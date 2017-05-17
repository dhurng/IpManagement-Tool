#!/usr/bin/env bash

################################################################
#
################################################################

export ETCDCTL=/opt/bin/etcdctl
export ETCDCTL_ENDPOINTS=https://127.0.0.1:4001
export ETCDCTL_CA_FILE=/etc/kubernetes/cert/ca.pem
export ETCDCTL_KEY_FILE=/etc/kubernetes/cert/etcd-key.pem
export ETCDCTL_CERT_FILE=/etc/kubernetes/cert/etcd.pem

export PIP_PATH=/softlayer/subnets/portable
export PIP_EMPTY=0 # Assume the PIP is in use

# if the definition of empty record changes
# then need to add that here and increment PUP_NUM_ENTRY
PIP_EMPTY_REC[0]='{"recordID": 0, "hostname": "", "namespace": ""}'
PIP_EMPTY_REC[1]='{"recordID":0,"hostname":"","namespace":""}'
PIP_EMPTY_REC[2]='{"recordID": -1, "hostname": "", "namespace": ""}'
PIP_EMPTY_REC[3]='{"recordID":-1,"hostname":"none"}' # prod1
export PIP_NUM_EMPTY=4

export PIP_RECORD=''
export PIP=''
export ALL_PIPS=''
export PIP_LIST=''

################################################################
#
getAllPips()
{
    ALL_PIPS=$(${ETCDCTL} ls /softlayer/subnets/portable|sort)
    # Only set PIP_LIST if unset
    if [[ -z "$PIP_LIST" ]]; then
        PIP_LIST=$(echo "${ALL_PIPS}" | sed -e 's,/softlayer/subnets/portable/,,')
    fi

}

################################################################
listAllPips()
{
    echo "INFO: => ${ETCDCTL} ls /softlayer/subnets/portable|sort"
    echo "$ALL_PIPS" # | sed -e 's/^/INFO: /'
}

################################################################
#
echoPipRecord()
{
    if (( DELIMETER_FLAG )); then
      if [[ ${PIP} =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
        echo "${PIP}:${PIP_EXISTS}:${PIP_EMPTY}:${PIP_RECORD}"
      fi
    else
      echo "pip:${PIP}:exists:${PIP_EXISTS} empty:${PIP_EMPTY} record:${PIP_RECORD}"
    fi
}

################################################################
#
listPipDetails()
{

    for PIP in $PIP_LIST; do
        getPipRecord
        if (( PIP_EXISTS )); then
            echoPipRecord
        fi
    done
}

################################################################
#
getPipRecord()
{
    local PS3=getPipRecord
    local NUM
    PIP_RECORD=''
    PIP_EXISTS=0
    PIP_EMPTY=0 # Only vaid if PIP_EXISTS

    if [[ -n "$PIP" ]]; then
        PIP_RECORD="$(${ETCDCTL} get ${PIP_PATH}/$PIP)"

        if [[ -n "${PIP_RECORD}" ]]; then
            PIP_EXISTS=1
            for (( NUM=0; NUM < PIP_NUM_EMPTY; NUM +=1 ));do
                if [[ "${PIP_EMPTY_REC[$NUM]}" == "${PIP_RECORD}" ]]; then
                    PIP_EMPTY=1
                fi
                #echo "$NUM - $PIP_EMPTY"
                #sleep 5
            done
        fi
    fi
}

################################################################
#
backupPipDir()
{
    echo "INFO: backupPipDir not implemented"
}

################################################################
#
mkPipRecord()
{
    if [[ -n "${PIP_LIST}" ]]; then
        for PIP in ${PIP_LIST}; do
            getPipRecord
            if (( ! PIP_EXISTS )); then
                ${ETCDCTL} mk ${PIP_PATH}/$PIP "${PIP_EMPTY_REC[0]}"
            else
                echo -n "WARNING mkPipRecord: => "
                echoPipRecord
            fi
        done
    else
        echo "FATAL mkPip PIP_LIST is empty"
    fi
}

################################################################
#
rmPipRecord()
{
    if [[ -n "${PIP_LIST}" ]]; then
        for PIP in ${PIP_LIST}; do
            getPipRecord
            if (( PIP_EXISTS )); then
                if (( PIP_EMPTY || USE_FORCE )); then
                    ${ETCDCTL} rm ${PIP_PATH}/$PIP
                    echo "INFO $PIP removed"
                else
                    echo "FATAL: ${PIP_PATH}/$PIP is in use"
                    echoPipRecord
                fi
            else
                echo "FATAL: ${PIP_PATH}/$PIP does not exist"
            fi
        done
    else
        echo "FATAL: mkPip PIP_LIST is empty"
    fi
}

################################################################
#
updatePipRecord()
{
    if [[ -n "${NEW_PIP_RECORD}" ]]; then
        if [[ -n "${PIP_LIST}" ]]; then
            for PIP in ${PIP_LIST}; do
                getPipRecord
                if (( PIP_EXISTS )); then
                    if (( PIP_EMPTY || USE_FORCE )); then
                        ${ETCDCTL} update ${PIP_PATH}/$PIP "${NEW_PIP_RECORD}"
                        echo "INFO $PIP updated"
                    else
                        echo "FATAL: ${PIP_PATH}/$PIP is in use"
                        echoPipRecord
                    fi
                else
                    echo "FATAL ${PIP_PATH}/$PIP does not exist"
                fi
            done
        else
            echo "FATAL: mkPip PIP_LIST is empty"
        fi
    else
        echo "FATAL You must provide a pip record"
    fi
}

################################################################
#
# main()
{
    # Parse input options
    declare    action="listAllPips" # Default action
    declare    PIP_LIST=""
    declare    NEW_PIP_RECORD=""
    declare -i USE_FORCE=0
    declare    DELIMETER_FLAG=0

    # Optional arguments must be entered before the action
    declare    opt=""
    declare    OPTARG=""
    declare -i OPTIND=1

    while getopts a:Fp:r:xd opt
    do
        case $opt in
            a) action="$OPTARG" ;;
            d) DELIMETER_FLAG=1 ;;
            F) USE_FORCE=1 ;;
            p) PIP_LIST="$OPTARG" ;;
            r) NEW_PIP_RECORD="$OPTARG" ;;
            x) set -x ; echo "INFOR set -x" ;;
        esac
    done
    shift $((OPTIND - 1))

    if [[ -n "${NEW_PIP_RECORD}" ]]; then
        echo "new !${NEW_PIP_RECORD}!"
    fi
    getAllPips

    case $action in
        listAllPips)    listAllPips ;;
        listPipDetails) listPipDetails ;;
#        echoPipRecord)  echoPipRecord ;;
#        getPipRecord)   getPipRecord ;;
        backupPipDir)   backupPipDir ;;
        mkPipRecord)    mkPipRecord ;;
        rmPipRecord)    rmPipRecord ;;
        updatePipRecord)    updatePipRecord ;;
        *) echo "Fatal $action is not supported" ;;
    esac

    if [[ -f /tmp/managePip.sh ]]; then
        rm /tmp/managePip.sh
    fi
}
