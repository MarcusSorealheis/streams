#! /bin/bash

set -x
NAMESPACE="${1:-}"
CHART_VERSION="${2:-5.0.0}"

if [ -z "${NAMESPACE}" ]; then
  echo "Please pass the namespace to install into as the first parameter"
  exit 1
fi

lw_helm_repo="lucidworks"

echo -e "\nAdding the Lucidworks chart repo to helm repo list"

helm repo list | grep "https://charts.lucidworks.com"
if [ $? ]; then
  helm repo add ${lw_helm_repo} https://charts.lucidworks.com
fi

helm repo update

echo -e "\nInstalling Fusion 5.0 Helm chart ${CHART_VERSION} into namespace ${NAMESPACE}"

helm install --namespace "${NAMESPACE}" -n "${NAMESPACE}" "${lw_helm_repo}/fusion" --version "${CHART_VERSION}" --set api-gateway.ingress.enabled=true --set api-gateway.ingress.host="${NAMESPACE}.streams.lucidworks.com"
