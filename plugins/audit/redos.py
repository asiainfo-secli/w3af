'''
redos.py

Copyright 2006 Andres Riancho

This file is part of w3af, w3af.sourceforge.net .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

'''
from __future__ import with_statement

import core.controllers.outputManager as om

import core.data.kb.vuln as vuln
import core.data.kb.info as info
import core.data.constants.severity as severity
import core.data.kb.knowledgeBase as kb

from core.controllers.plugins.audit_plugin import AuditPlugin
from core.data.fuzzer.fuzzer import create_mutants


class redos(AuditPlugin):
    '''
    Find ReDoS vulnerabilities.
    
    @author: Sebastien Duquette ( sebastien.duquette@gmail.com )
    @author: Andres Riancho (andres.riancho@gmail.com)
    '''
    def __init__(self):
        AuditPlugin.__init__(self)
        
        # Some internal variables
        # The wait time of the unmodified request
        self._original_wait_time = 0
        
        # The wait time of the first test I'm going to perform
        self._wait_time = 1
    
    def audit(self, freq ):
        '''
        Tests an URL for ReDoS vulnerabilities using time delays.
        
        @param freq: A fuzzable_request
        '''
        #
        #   We know for a fact that PHP is NOT vulnerable to this attack
        #
        #   TODO: Add other frameworks that are not vulnerable!
        #
        for powered_by in kb.kb.get('server_header','poweredByString'):
            if 'php' in powered_by.lower():
                return
        
        if 'php' in freq.getURL().getExtension().lower():
            return
        
        # Send the fuzzable_request without any fuzzing, so we can measure the
        # response time of this script in order to compare it later
        res = self._uri_opener.send_mutant(freq, grep=False)
        self._original_wait_time = res.getWaitTime()
        
        # Prepare the strings to create the mutants
        patterns_list = self._get_wait_patterns(run=1)
        mutants = create_mutants( freq , patterns_list )
        
        self._send_mutants_in_threads(self._uri_opener.send_mutant,
                                      mutants,
                                      self._analyze_wait)
                
    def _analyze_wait( self, mutant, response ):
        '''
        Analyze results of the _send_mutant method that was sent in the audit method.
        '''
        #
        #   I will only report the vulnerability once.
        #
        if self._has_no_bug(mutant, pname='preg_replace',
                            kb_varname='preg_replace'):
            
            if response.getWaitTime() > (self._original_wait_time + self._wait_time) :
                
                # This could be because of a ReDoS vuln, an error that generates a delay in the
                # response or simply a network delay; so I'll resend changing the length and see
                # what happens.
                
                first_wait_time = response.getWaitTime()
                
                # Replace the old pattern with the new one:
                original_wait_param = mutant.getModValue()
                more_wait_param = original_wait_param.replace( 'X', 'XX' )
                more_wait_param = more_wait_param.replace( '9', '99' )
                mutant.setModValue( more_wait_param )
                
                # send
                response = self._uri_opener.send_mutant(mutant)
                
                # compare the times
                if response.getWaitTime() > (first_wait_time * 1.5):
                    # Now I can be sure that I found a vuln, I control the time of the response.
                    v = vuln.vuln( mutant )
                    v.setPluginName(self.getName())
                    v.setName( 'ReDoS vulnerability' )
                    v.setSeverity(severity.MEDIUM)
                    v.setDesc( 'ReDoS was found at: ' + mutant.foundAt() )
                    v.setDc( mutant.getDc() )
                    v.set_id( response.id )
                    v.setURI( response.getURI() )
                    kb.kb.append_uniq( self, 'redos', v )

                else:
                    # The first delay existed... I must report something...
                    i = info.info()
                    i.setPluginName(self.getName())
                    i.setName('Possible ReDoS vulnerability')
                    i.set_id( response.id )
                    i.setDc( mutant.getDc() )
                    i.setMethod( mutant.get_method() )
                    msg = 'A possible ReDoS was found at: ' + mutant.foundAt() 
                    msg += ' . Please review manually.'
                    i.setDesc( msg )
                    
                    # Just printing to the debug log, we're not sure about this
                    # finding and we don't want to clog the report with false
                    # positives
                    om.out.debug( str(i) )

    
    def end(self):
        '''
        This method is called when the plugin wont be used anymore.
        '''
        self.print_uniq( kb.kb.get( 'redos', 'redos' ), 'VAR' )
    
    def _get_wait_patterns( self, run ):
        '''
        @return: This method returns a list of commands to try to execute in order
        to introduce a time delay.
        '''
        patterns = []
        
        patterns.append('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaX!')
        patterns.append('a@a.aaaaaaaaaaaaaaaaaaaaaaX!')
        patterns.append('1111111111111111111111111111111119!')
        
        return patterns
    
    def get_plugin_deps( self ):
        '''
        @return: A list with the names of the plugins that should be run before the
        current one.
        '''
        return ['infrastructure.server_header']
    
    def get_long_desc( self ):
        '''
        @return: A DETAILED description of the plugin functions and features.
        '''
        return '''
        This plugin finds ReDoS (regular expression DoS) vulnerabilities as
        explained here:
                    - http://en.wikipedia.org/wiki/ReDoS 
        '''
