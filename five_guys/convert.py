#!/usr/bin/env python

import csv
import argparse

from stix.ttp import TTP, Resource
from stix.ttp.infrastructure import Infrastructure

import cybox.utils

from datetime import datetime
from dateutil.tz import tzutc
from stix.indicator import Indicator
from stix.indicator.sightings import Sighting

from stix.core import STIXPackage, STIXHeader
from stix.common import (InformationSource, Identity, RelatedObservable,
                         VocabString)
from cybox.common import ToolInformationList, Time
from cybox.common import Hash
from stix.common.vocabs import VocabString

from cybox.objects.email_message_object import EmailMessage,Attachments,AttachmentReference
from cybox.objects.socket_address_object import SocketAddress
from cybox.objects.port_object import Port
from cybox.objects.domain_name_object import DomainName
from cybox.objects.file_object import File
from cybox.objects.mutex_object import Mutex
from cybox.objects.http_session_object import *
from cybox.objects.win_registry_key_object import *

from stix.common.kill_chains import KillChainPhase, KillChain, KillChainPhaseReference

def main():
    # get args
    parser = argparse.ArgumentParser ( description = "Parse a given CSV and output STIX XML" 
    , formatter_class=argparse.ArgumentDefaultsHelpFormatter )

    parser.add_argument("--infile","-f", help="input CSV", default = "in.csv")

    args = parser.parse_args()

    # setup header
    contain_pkg = STIXPackage()
    stix_header = STIXHeader()
    stix_header.title = "Indicators"
    stix_header.add_package_intent ("Indicators")
    # XXX add Information_Source and Handling
    contain_pkg.stix_header = stix_header


    # create kill chain with three options (pre, post, unknown), relate as needed
    pre = KillChainPhase(phase_id="stix:KillChainPhase-1a3c67f7-5623-4621-8d67-74963d1c5fee", name="Pre-infection indicator", ordinality=1)
    post = KillChainPhase(phase_id="stix:KillChainPhase-d5459305-1a27-4f50-9875-23793d75e4fe", name="Post-infection indicator", ordinality=2)
    chain = KillChain(id_="stix:KillChain-3fbfebf2-25a7-47b9-ad8b-3f65e56e402d", name="Degenerate Cyber Kill Chain"  )
    chain.definer = "U5"

    chain.kill_chain_phases = [pre, post]
    contain_pkg.ttps.kill_chains.append(chain)

    # read input data
    fd = open (args.infile, "rb") 
    infile = csv.DictReader(fd)

    for row in infile:
        # create indicator for each row
        error = False
        ind = Indicator()
        ind.add_alternative_id(row['ControlGroupID'])
        ind.title = "Indicator with ID " + row['IndicatorID'] 
        ind.description = row['Notes']
        ind.producer = InformationSource()
        ind.producer.description = row['Reference']

        # XXX unknown purpose for 'Malware' field - omitted
            # if the field denotes a specific malware family, we might relate as 'Malware TTP' to the indicator

        # set chain phase
        if 'Pre' in row['Infection Type']:
            ind.kill_chain_phases.append(KillChainPhaseReference(phase_id="stix:KillChainPhase-1a3c67f7-5623-4621-8d67-74963d1c5fee",kill_chain_id="stix:KillChain-3fbfebf2-25a7-47b9-ad8b-3f65e56e402d"))
        elif 'Post' in row['Infection Type']:
            ind.kill_chain_phases.append(KillChainPhaseReference(phase_id="stix:KillChainPhase-1a3c67f7-5623-4621-8d67-74963d1c5fee",kill_chain_id="stix:KillChain-3fbfebf2-25a7-47b9-ad8b-3f65e56e402d"))
 

        ind_type = row['Indicator Type']
        if 'IP' in ind_type:
            
            ind.add_indicator_type( "IP Watchlist")
            ind_obj = SocketAddress()
            ind_obj.ip_address = row['Indicator']
            ind_obj.ip_address.condition= "Equals"
            if row['indValue']:
                port = Port()
                # pull port out, since it's in form "TCP Port 42"
                port.port_value = row['indValue'].split()[-1] 
                port.layer4_protocol = row['indValue'].split()[0] 
                port.port_value.condition= "Equals"
                ind_obj.port = port


        elif 'Domain' in ind_type:
            ind.add_indicator_type ("Domain Watchlist")
            ind_obj = DomainName()
            ind_obj.value = row['Indicator']
            ind_obj.value.condition= "Equals"

        elif 'Email' in ind_type:
            # parse out which part of the email is being
            # i.e. "Sender: attach | Subject: whatever"
            tag = row['Indicator'].split(':')[0]
            val = row['Indicator'].split(':')[1]
            ind.add_indicator_type ("Malicious E-mail")
            ind_obj = EmailMessage()
            
            if "Subject" in tag:
                ind_obj.subject = val
                ind_obj.subject.condition= "Equals"
            elif "Sender" in tag:
                ind_obj.sender = val
                ind_obj.sender.condition= "Equals"
            
            elif "Attachment" in tag:
                # make inline File to store filename 
                file_obj = File()
                file_obj.id_ = cybox.utils.create_id(prefix="File")
                file_obj.file_name = val
                file_obj.file_name.condition = "Equals"
                ind_obj.add_related(file_obj, "Contains")
                
                attach = Attachments()
                attach.append(file_obj.id_)
                
                ind_obj.attachments = attach
                
        elif 'User Agent' in ind_type:
            ind.add_indicator_type( VocabString(row['Indicator Type']))
            
            fields = HTTPRequestHeaderFields()
            fields.user_agent = row['Indicator']
            fields.user_agent.condition = "Equals"
            header = HTTPRequestHeader()
            header.parsed_header = fields

            thing = HTTPRequestResponse()
            thing.http_client_request = HTTPClientRequest()
            thing.http_client_request.http_request_header = header

            ind_obj = HTTPSession()
            ind_obj.http_request_response = [thing]
            
        elif 'URI' in ind_type:
            ind.add_indicator_type( VocabString(row['Indicator Type']))
    
            thing = HTTPRequestResponse()
            thing.http_client_request = HTTPClientRequest()
            thing.http_client_request.http_request_line = HTTPRequestLine()
            thing.http_client_request.http_request_line.http_method = row['Indicator'].split()[0]
            thing.http_client_request.http_request_line.http_method.condition = "Equals" 
            thing.http_client_request.http_request_line.value = row['Indicator'].split()[1]
            thing.http_client_request.http_request_line.value.condition = "Equals" 

            ind_obj = HTTPSession()
            ind_obj.http_request_response = [thing]


        elif 'File' in ind_type:
            ind.add_indicator_type( VocabString(row['Indicator Type']))
            ind_obj = File()
            ind_obj.file_name = row['Indicator']
            ind_obj.file_name.condition = "Equals"
            digest = Hash()
            # XXX assumes that hash digests are stored in this field in real data
            digest.simple_hash_value = row['indValue'].strip()
            digest.simple_hash_value.condition = "Equals"
            digest.type_.condition = "Equals"

            ind_obj.add_hash(digest)

        elif 'Registry' in ind_type:
            ind.add_indicator_type( VocabString(row['Indicator Type']))
            
            ind_obj = WinRegistryKey()
            keys = RegistryValues()
            key = RegistryValue()
            key.name = row['Indicator']
            key.name.condition = "Equals"
            key.data = row['indValue']
            key.data.condition = "Equals"
            keys.append(key)
            ind_obj.values = keys

        elif 'Mutex' in ind_type:
            ind.add_indicator_type (VocabString(row['Indicator Type']))
            ind_obj = Mutex()
            ind_obj.name = row['Indicator']
            ind_obj.name.condition= "Equals"

        else:
            print "ERR type not supported: " + ind_type + " <- will be omitted from output"
            error = True

        # finalize indicator
        if not error:
            ind.add_object(ind_obj)
            contain_pkg.add_indicator(ind)

    # DONE looping

    print contain_pkg.to_xml() 

if __name__ == "__main__":
    main()
