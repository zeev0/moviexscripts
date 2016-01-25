#!/usr/bin/python3
# -*- coding: utf-8 -*- #
#
# inspired by thricedotted's bot.py
#
# moviexscripts.py
# ------

import os
import sys
import random
import tweepy
import time
import logging
import pickle as pickle

from http.client import IncompleteRead

class Bot:

    MINUTE = 60
    HOUR = 60 * MINUTE
    DAY = 24 * HOUR

    MAX_FAILURES = 30

    def __init__(self, filename, name=''):
        # name of the bot is not required because we can get that from twitter's api
        # configuration dict and state dict are the primary data flow controllers
        #      configs should not be changed once set
        #      states should be change to reflect the bot's current state
        self.config = {}
        self.state = {}

        #################################
        # REQUIRED: LOGIN DETAILS HERE! #
        #################################
        self.config['api_key'] = ''
        self.config['api_secret'] = ''
        self.config['access_key'] = ''
        self.config['access_secret'] = ''

        # twitter authentication
        auth = tweepy.OAuthHandler(self.config['api_key'], self.config['api_secret'])
        auth.set_access_token(self.config['access_key'], self.config['access_secret'])
        self.api = tweepy.API(auth)
        self.id = self.api.me().id
        self.screen_name = self.config['name'] = self.api.me().screen_name

        # logging
        self.config['logging_level'] = logging.DEBUG
        logging.basicConfig(format='%(asctime)s | %(levelname)s: %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', 
            filename=self.screen_name + '.log',
            level=self.config['logging_level'])

        logging.info('Twitter handshake succesful -- Initializing bot...')

        # tweet interval
        self.config['tweet_interval_range'] = (Bot.MINUTE, 2*Bot.MINUTE) 
        self.config['tweet_interval'] = random.randint(*self.config['tweet_interval_range'])
        self.config['sleep_time'] = Bot.MINUTE//5 

        # file i/o
        self.config['storage'] = FileStorage()

        self.config['filename'] = filename

        # recover state
        try:
            with self.config['storage'].read(self.screen_name) as f:
                self.state = pickle.load(f)
        except IOError:
            pass
        except EOFError:
            pass

        if 'script' not in self.state:
            self.load_script(filename)
        if 'last_tweet_time' not in self.state:
            self.state['last_tweet_time'] = 1
        if 'failure_count' not in self.state:
            self.state['failure_count'] = 0

        logging.info('Bot initialized!')

    def save_state(self):
        with self.config['storage'].write(self.screen_name) as f:
            pickle.dump(self.state, f)
            self.log('Bot state saved')

    def load_script(self, filename):
        with open(filename) as f:
            print('opened ', f)
            self.state['script'] = f.read().split('\n')

    def log(self, message, level=logging.INFO):
        if level == logging.ERROR:
            logging.error(message)
        else:
            logging.info(message)


    def log_tweepy_error(self, message, e):
        try:
            e_message = e.message[0]['message']
            code = e.message[0]['code']
            self.log("{}: {} ({})".format(message, e_message, code), level=logging.ERROR)
        except:
            self.log(message, e)


    def post_tweet(self):
        """
        posts the next tweet from the script
        """
        if len(self.state['script']) == 0:
            self.log('The Script is empty! Exiting...')
            exit()
        
        tweet_text = self.state['script'].pop(0)
        tweet_text = self.prep_tweet(tweet_text)
        tweet_success = False
        while not tweet_success:
            try:
                print('tweeting ', tweet_text)
                self.api.update_status(tweet_text)
                print('tweet success')
                self.log('Tweeting "{}"'.format(tweet_text))
                self.state['last_tweet_time'] = time.time()
                tweet_success = True
            except tweepy.TweepError as e:
                self.state['failure_count'] += 1
                self.log_tweepy_error('Can\'t post status', e)
                time.sleep(5) # wait a bit before we try to tweet again
                if self.state['failure_count'] > Bot.MAX_FAILURES:
                    self.log('Maximum amount of failures('+ str(Bot.MAX_FAILURES) +') reached. Exiting...')
                    exit()


    def prep_tweet(self, tweet_text):
        words = tweet_text.split(' ')
        i = 0
        while i < len(words) and words[i].isupper() and words[i] != 'I':
            i += 1
        if i == 0: return tweet_text
        if i == len(words): return ' '.join(words)
        beginning = words[0:i]
        end = words[i:len(words)]
        tweet_text = ' '.join(beginning) + ': ' + ' '.join(end)
        return tweet_text
        
        
    def run(self):
        """
        run the bot
        """
        while True:
            # tweet to timeline on the correct interval
            if (time.time() - self.state['last_tweet_time']) > self.config['tweet_interval']:
                self.post_tweet()
                self.config['tweet_interval'] = random.randint(*self.config['tweet_interval_range'])
                self.log("Next tweet in {} seconds".format(self.config['tweet_interval']))
                self.save_state()
            logging.info("Sleeping for a bit...")
            print("sleeping...")
            time.sleep(self.config['sleep_time'])
        

class FileStorage(object):
    """
    Default storage adapter.

    Adapters must implement two methods: read(name) and write(name).
    """

    def read(self, name):
        """
        Return an IO-like object that will produce binary data when read from.
        If nothing is stored under the given name, raise IOError.
        """
        filename = self._get_filename(name)
        if os.path.exists(filename):
            logging.debug("Reading from {}".format(filename))
        else:
            logging.debug("{} doesn't exist".format(filename))
        return open(filename, 'rb')


    def write(self, name):
        """
        Return an IO-like object that will store binary data written to it.
        """
        filename = self._get_filename(name)
        if os.path.exists(filename):
            logging.debug("Overwriting {}".format(filename))
        else:
            logging.debug("Creating {}".format(filename))
        return open(filename, 'wb')


    def _get_filename(self, name):
        return '{}_state.pkl'.format(name)


# useful functions for preparing scripts
# the goal is to have a single, less than 140 char tweet, per line
def prep_script(filename):
    """ attempts to format a text file so that there is one tweet per line """
    f = open(filename)
    contents = f.read()
    contents = contents.split('\n\n')
    for i in range(len(contents)):
        contents[i] = ' '.join(contents[i].split())
    contents = [x for x in contents if (x and len(x) <= 140)]
    return contents


def write_script_out(contents, filename):
    """ writes a given script (a list) out to a file """
    with open(filename, 'w') as f:
        for x in contents:
            f.write('%s\n' % x)


if __name__ == '__main__':
    ###########################################################################
    # Bot will use given input as filename to the formatted script, otherwise #
    # you can write it here                                                   #
    ###########################################################################
    filename = ''

    args = sys.argv.pop(0)
    if args:
       filename = args[0] 
    b = Bot(filename)
    b.run()
