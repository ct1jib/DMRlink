#!/usr/bin/env python
#
###############################################################################
#   Copyright (C) 2016  Cortney T. Buffington, N0MJS <n0mjs@me.com>
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software Foundation,
#   Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA
###############################################################################

# This is a sample application that uses the Repeater Call Monitor packets to display events in the IPSC
# NOTE: dmrlink.py MUST BE CONFIGURED TO CONNECT AS A "REPEATER CALL MONITOR" PEER!!!
# ALSO NOTE, I'M NOT DONE MAKING THIS WORK, SO UNTIL THIS MESSAGE IS GONE, DON'T EXPECT GREAT THINGS.

from __future__ import print_function
from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from twisted.internet import task
from binascii import b2a_hex as ahex

import datetime
import binascii
import dmrlink
from dmrlink import IPSC, systems
from dmr_utils.utils import get_alias, int_id

__author__      = 'Cortney T. Buffington, N0MJS'
__copyright__   = 'Copyright (c) 2013, 2014 Cortney T. Buffington, N0MJS and the K0USY Group'
__credits__     = 'Adam Fast, KC0YLK; Dave Kierzkowski KD8EYF'
__license__     = 'GNU GPLv3'
__maintainer__  = 'Cort Buffington, N0MJS'
__email__       = 'n0mjs@me.com'


try:
    from ipsc.ipsc_message_types import *
except ImportError:
    sys.exit('IPSC message types file not found or invalid')

status = True
rpt = True
nack = True

class rcmIPSC(IPSC):
    def __init__(self, _name, _config, _logger):
        IPSC.__init__(self, _name, _config, _logger)
        
    #************************************************
    #     CALLBACK FUNCTIONS FOR USER PACKET TYPES
    #************************************************
    #
    def call_mon_status(self, _data):
        if not status:
            return
        _source =   _data[1:5]
        _ipsc_src = _data[5:9]
        _seq_num =  _data[9:13]
        _ts =       _data[13]
        _status =   _data[15] # suspect [14:16] but nothing in leading byte?
        _rf_src =   _data[16:19]
        _rf_tgt =   _data[19:22]
        _type =     _data[22]
        _prio =     _data[23]
        _sec =      _data[24]
        
        _source = str(int_id(_source)) + ', ' + str(get_alias(_source, peer_ids))
        _ipsc_src = str(int_id(_ipsc_src)) + ', ' + str(get_alias(_ipsc_src, peer_ids))
        _rf_src = str(int_id(_rf_src)) + ', ' + str(get_alias(_rf_src, subscriber_ids))
        
        if _type == '\x4F' or '\x51':
            _rf_tgt = 'TGID: ' + str(int_id(_rf_tgt)) + ', ' + str(get_alias(_rf_tgt, talkgroup_ids))
        else:
            _rf_tgt = 'SID: ' + str(int_id(_rf_tgt)) + ', ' + str(get_alias(_rf_tgt, subscriber_ids))
        
        print('Call Monitor - Call Status')
        print('TIME:        ', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print('DATA SOURCE: ', _source)
        print('IPSC:        ', self._system)
        print('IPSC Source: ', _ipsc_src)
        print('Timeslot:    ', TS[_ts])
        try:
            print('Status:      ', STATUS[_status])
        except KeyError:
            print('Status (unknown): ', h(_status))
        try:
            print('Type:        ', TYPE[_type])
        except KeyError:
            print('Type (unknown): ', h(_type))
        print('Source Sub:  ', _rf_src)
        print('Target Sub:  ', _rf_tgt)
        print()
    
    def call_mon_rpt(self, _data):
        if not rpt:
            return
        _source    = _data[1:5]
        _ts1_state = _data[5]
        _ts2_state = _data[6]
        
        _source = str(int_id(_source)) + ', ' + str(get_alias(_source, peer_ids))
        
        print('Call Monitor - Repeater State')
        print('TIME:         ', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print('DATA SOURCE:  ', _source)
     
        try:
            print('TS1 State:    ', REPEAT[_ts1_state])
        except KeyError:
            print('TS1 State (unknown): ', h(_ts1_state))
        try:
            print('TS2 State:    ', REPEAT[_ts2_state])
        except KeyError:
            print('TS2 State (unknown): ', h(_ts2_state))
        print()
            
    def call_mon_nack(self, _data):
        if not nack:
            return
        _source = _data[1:5]
        _nack =   _data[5]
        
        _source = get_alias(_source, peer_ids)
        
        print('Call Monitor - Transmission NACK')
        print('TIME:        ', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print('DATA SOURCE: ', _source)
        try:
            print('NACK Cause:  ', NACK[_nack])
        except KeyError:
            print('NACK Cause (unknown): ', h(_nack))
        print()
    
    def repeater_wake_up(self, _data):
        _source = _data[1:5]
        _source_name = get_alias(_source, peer_ids)
        print('({}) Repeater Wake-Up Packet Received: {} ({})' .format(self._system, _source_name, int_id(_source)))


if __name__ == '__main__':
    import argparse
    import os
    import sys
    import signal
    from dmr_utils.utils import try_download, mk_id_dict
    
    import dmrlink_log
    import dmrlink_config
    
    # Change the current directory to the location of the application
    os.chdir(os.path.dirname(os.path.realpath(sys.argv[0])))

    # CLI argument parser - handles picking up the config file from the command line, and sending a "help" message
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', action='store', dest='CFG_FILE', help='/full/path/to/config.file (usually dmrlink.cfg)')
    cli_args = parser.parse_args()

    if not cli_args.CFG_FILE:
        cli_args.CFG_FILE = os.path.dirname(os.path.abspath(__file__))+'/dmrlink.cfg'
    
    # Call the external routine to build the configuration dictionary
    CONFIG = dmrlink_config.build_config(cli_args.CFG_FILE)
    
    # Call the external routing to start the system logger
    logger = dmrlink_log.config_logging(CONFIG['LOGGER'])

    logger.info('DMRlink \'rcm.py\' (c) 2013, 2014 N0MJS & the K0USY Group - SYSTEM STARTING...')
    
    # ID ALIAS CREATION
    # Download
    if CONFIG['ALIASES']['TRY_DOWNLOAD'] == True:
        # Try updating peer aliases file
        result = try_download(CONFIG['ALIASES']['PATH'], CONFIG['ALIASES']['PEER_FILE'], CONFIG['ALIASES']['PEER_URL'], CONFIG['ALIASES']['STALE_TIME'])
        logger.info(result)
        # Try updating subscriber aliases file
        result = try_download(CONFIG['ALIASES']['PATH'], CONFIG['ALIASES']['SUBSCRIBER_FILE'], CONFIG['ALIASES']['SUBSCRIBER_URL'], CONFIG['ALIASES']['STALE_TIME'])
        logger.info(result)
        
    # Make Dictionaries
    peer_ids = mk_id_dict(CONFIG['ALIASES']['PATH'], CONFIG['ALIASES']['PEER_FILE'])
    if peer_ids:
        logger.info('ID ALIAS MAPPER: peer_ids dictionary is available')
        
    subscriber_ids = mk_id_dict(CONFIG['ALIASES']['PATH'], CONFIG['ALIASES']['SUBSCRIBER_FILE'])
    if subscriber_ids:
        logger.info('ID ALIAS MAPPER: subscriber_ids dictionary is available')
    
    talkgroup_ids = mk_id_dict(CONFIG['ALIASES']['PATH'], CONFIG['ALIASES']['TGID_FILE'])
    if talkgroup_ids:
        logger.info('ID ALIAS MAPPER: talkgroup_ids dictionary is available')
    
    # Shut ourselves down gracefully with the IPSC peers.
    def sig_handler(_signal, _frame):
        logger.info('*** DMRLINK IS TERMINATING WITH SIGNAL %s ***', str(_signal))
    
        for system in systems:
            this_ipsc = systems[system]
            logger.info('De-Registering from IPSC %s', system)
            de_reg_req_pkt = this_ipsc.hashed_packet(this_ipsc._local['AUTH_KEY'], this_ipsc.DE_REG_REQ_PKT)
            this_ipsc.send_to_ipsc(de_reg_req_pkt)
        reactor.stop()

    # Set signal handers so that we can gracefully exit if need be
    for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGQUIT]:
        signal.signal(sig, sig_handler)
    
    
    # INITIALIZE AN IPSC OBJECT (SELF SUSTAINING) FOR EACH CONFIGUED IPSC
    for system in CONFIG['SYSTEMS']:
        if CONFIG['SYSTEMS'][system]['LOCAL']['ENABLED']:
            systems[system] = rcmIPSC(system, CONFIG, logger)
            reactor.listenUDP(CONFIG['SYSTEMS'][system]['LOCAL']['PORT'], systems[system], interface=CONFIG['SYSTEMS'][system]['LOCAL']['IP'])
    
    reactor.run()