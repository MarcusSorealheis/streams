import time
import httplib2, json
import webapp2
import time, datetime

from lib.dateutil import parser as DUp

import config
import web.forms as forms
from web.basehandler import BaseHandler
from web.basehandler import user_required, admin_required
from web.models.models import User, Stream, Instance
from lib import slack
from lib import utils

class AdminStreamsAPIHandler(BaseHandler):
    # disable csrf check in basehandler
    csrf_exempt = True
    def post(self, sid=None):
        # permanance
        try:
            prod = self.request.get('prod')
            prod = "true"
        except:
            prod = "false" # will be preemptible

        # topic (stackexchange subdomain, for now)
        try:
            topic = self.request.get('topic')
        except:
            topic = "none"

        # check token
        token = self.request.get('token')
        if token != "":
            user_info = User.get_by_token(token)

            # look up streams
            stream = Stream.get_by_sid(sid)
            if not stream:
                params = {"response": "fail", "message": "stream %s does not exist on these endpoints" % sid}
                return self.render_template('api/response.json', **params)

            # look up user's instances
            db_instances = Instance.get_all()

            # check the user's limits
            instance_count = 0
            for db_instance in db_instances:
                # limit to instances the user has started (doing it this way because can't figure out ndb indexing)
                if db_instance.user == user_info.key:
                    instance_count = instance_count + 1

            # warn and redirect if limit is reached
            if (instance_count + 1) > user_info.max_instances:
                params = {"response": "fail", "message": "max instances reached for provided token"}
                return self.render_template('api/response.json', **params)

            # make the instance call to the control box
            http = httplib2.Http(timeout=10)

            # where and who created it
            if config.isdev:
                iuser = "%s-%s" % ("dev", user_info.username)
            else:
                iuser = "%s-%s" % ("prod", user_info.username)

            url = '%s/api/stream/%s?token=%s&user=%s&topic=%s&prod=%s' % (
                config.fastener_host_url,
                sid,
                config.fastener_api_token,
                iuser,
                topic,
                prod
            )

            try:
                # pull the response back TODO add error handling
                # CREATE HAPPENS HERE
                response, content = http.request(url, 'POST', None, headers={})
                gcinstance = json.loads(content)
                name = gcinstance['instance']
                password = gcinstance['password']

                if name == "failed":
                    raise Exception("Instance start was delayed due to limits. Try again in a few minutes.")

                # set up an instance
                instance = Instance(
                    name = name,
                    status = "PROVISIONING",
                    user = user_info.key,
                    stream = stream.key,
                    password = password,
                    expires = datetime.datetime.now() + datetime.timedelta(0, 604800),
                    started = datetime.datetime.now()
                )
                instance.put()

                try:
                    slack.slack_message("Instance type %s created for %s!" % (stream.name, user_info.username))
                except:
                    print "slack failing"

                # give the db a second to update
                if config.isdev:
                    time.sleep(3)

                params = {'instance': instance}
                
                self.response.headers['Content-Type'] = "application/json"
                return self.render_template('api/instance.json', **params)

            except Exception as ex:
                # the horror
                params = {"response": "fail", "message": "exception thrown: %s" % ex}
                return self.render_template('api/response.json', **params)   


            self.response.headers['Content-Type'] = "application/json"
            return self.render_template('api/stream.json', **params)
        # check token

        # no token, no user, no data
        params = {"response": "fail", "message": "must include [token] with a valid token"}
        return self.render_template('api/response.json', **params)


    def get(self, sid=None):
        # check token
        token = self.request.get('token')
        if token != "":
            user_info = User.get_by_token(token)

        # look up streams
        stream = Stream.get_by_sid(sid)

        params = {
            'stream': stream
        }
        self.response.headers['Content-Type'] = "application/json"
        return self.render_template('api/stream.json', **params)


class AdminInstancesAPIHandler(BaseHandler):
    def get(self, name=None):
        # check token
        token = self.request.get('token')
        if token != "":
            user_info = User.get_by_token(token)

            if user_info:
                instance = Instance.get_by_name(name)

                try:
                    if instance.user == user_info.key:
                        params = {
                            'instance': instance
                        }
                        self.response.headers['Content-Type'] = "application/json"
                        return self.render_template('api/instance.json', **params)
                except Exception as ex:
                    print "error %s" % ex 
                    print "instance %s not found" % name

                params = {"response": "fail", "message": "[token] read access denied"}
                return self.render_template('api/response.json', **params)
            
        # no token, no user, no data
        params = {"response": "fail", "message": "must include [token] parameter with a valid token"}
        return self.render_template('api/response.json', **params)
        

class AdminStreamsHandler(BaseHandler):
    @user_required
    @admin_required
    def get(self, sid=None):
        # lookup user's auth info
        user_info = User.get_by_id(long(self.user_id))

        # look up streams
        streams = Stream.get_all()

        params = {
            'streams': streams
        }

        return self.render_template('admin/streams.html', **params)


    @user_required
    @admin_required
    def delete(self, stream_id=None):
        # delete the entry from the db
        stream = Stream.get_by_id(long(stream_id))
        sid = stream.sid

        if stream:
            stream.key.delete()
            self.add_message('Stream successfully deleted!', 'success')
        else:
            self.add_message('Something went horribly wrong somewhere!', 'warning')

        # hangout for a second
        if config.isdev:
            time.sleep(1)

        params = {"response": "success", "message": "stream %s deleted" % sid}
        return self.render_template('api/response.json', **params)
 

    @user_required
    @admin_required
    def post(self):
        if not self.form.validate():
            self.add_message('Form did not validate. Try again!', 'error')
            return self.get()

        # pull the github token out of the social user db
        user_info = User.get_by_id(long(self.user_id))
        
        # load values out of the form, including whether the gist should be public or not
        sid = self.form.sid.data.strip()
        name = self.form.name.data.strip()
        description = self.form.description.data.strip()
        tgzfile = self.form.tgzfile.data.strip()
        fusion_version = self.form.fusion_version.data.strip()
        github_repo = self.form.github_repo.data.strip()
        app_stub = self.form.app_stub.data.strip()
        labs_link = self.form.labs_link.data.strip()

        # save the stream          
        stream = Stream(
            sid = sid,
            name = name,
            description = description,
            tgzfile = tgzfile,
            fusion_version = fusion_version,
            github_repo = github_repo,
            app_stub = app_stub,
            labs_link = labs_link
        )

        stream.put()

        # give the db a second or two to update
        time.sleep(1)

        self.add_message('Stream %s successfully created!' % name, 'success')
        params = {}
        return self.redirect_to('admin-streams', **params)


    @webapp2.cached_property
    def form(self):
        return forms.StreamForm(self)


class AdminInstancesHandler(BaseHandler):
    @user_required
    @admin_required
    def get(self):
        # lookup user's auth info
        user_info = User.get_by_id(long(self.user_id))

        # look up instances, then patch them for hotstart support
        pinstances = []
        instances = Instance.get_all()
        for instance in instances:
            try:
                username_patch = instance.user.get().username 
            except:
                username_patch = "#HOTSTART#" # no self

            pinstance = {
                "name": instance.name,
                "status": instance.status,
                "username_patch": username_patch,
                "created": instance.created,
                "expires": instance.expires,
                "key": instance.key
            }
            pinstances.append(pinstance)

        params = {
            'instances': pinstances
        }

        return self.render_template('admin/instances.html', **params)

    @user_required
    @admin_required
    def delete(self, instance_id=None):
        # delete instance
        instance = Instance.get_by_id(long(instance_id))
        name = instance.name
        
        # kill it via API call and delete via API
        if instance:
            # make the instance call to the control box
            http = httplib2.Http(timeout=10)
            url = '%s/api/instance/%s/delete?token=%s' % (
                config.fastener_host_url, 
                name,
                config.fastener_api_token
            )

            # pull the response back TODO add error handling
            response, content = http.request(url, 'GET', None, headers={})

            # delete if google returns pending
            if json.loads(content)['status'] == "PENDING":
                instance.key.delete()
        else:
            pass
            # TODO implement this, even thought it's likely not to happen

        # hangout for a second
        if config.isdev:
            time.sleep(1)

        params = {"response": "success", "message": "instance %s deleted" % name}
        return self.render_template('api/response.json', **params)
 

class AdminUsersHandler(BaseHandler):
    @user_required
    @admin_required
    def get(self):
        # lookup user's auth info
        user_info = User.get_by_id(long(self.user_id))

        # look up users
        users = User.get_all()

        params = {
            'users': users
        }

        return self.render_template('admin/users.html', **params)

    @user_required
    @admin_required
    def post(self):
        uid = self.request.get('uid')
        superuser = self.request.get('super')

        # lookup user's auth info
        user_info = User.get_by_id(long(uid))

        # lookup user's auth info
        loggedin_user_info = User.get_by_id(long(self.user_id))

        # only allow kordless to modify kordless
        if user_info.username == "kordless" and user_info.username != loggedin_user_info.username:
            params = {"response": "fail", "message": "you can not touch that user"}
            self.response.set_status(402)
            return self.render_template('api/response.json', **params)

        # only allow erikhatcher to modify erikhatcher
        if user_info.username == "erikhatcher" and user_info.username != loggedin_user_info.username:
            params = {"response": "fail", "message": "you can not touch that user"}
            self.response.set_status(402)
            return self.render_template('api/response.json', **params)

        if user_info and superuser == "1":
            user_info.superuser = True
            user_info.max_instances = 10
            user_info.put()
        elif user_info:
            user_info.superuser = False
            user_info.max_instances = 3 # max instances are set here and in model for user
            user_info.put()

        params = {"response": "success", "message": "user %s modified" % uid}
        return self.render_template('api/response.json', **params)


class AdminUsersExportHandler(BaseHandler):
    @user_required
    @admin_required
    def get(self):
        # lookup user's auth info
        user_info = User.get_by_id(long(self.user_id))

        # look up usrs
        users = User.get_all()

        params = {
            'users': users
        }

        # mime it up
        self.response.headers['Content-Type'] = "text/csv"
        self.response.headers['Content-Disposition'] = "attachment; filename=users.csv"
        return self.render_template('admin/user.csv', **params)