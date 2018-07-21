import json
import sys
import requests
from optparse import OptionParser
import redis
import kafka
from functools import partial
from trend.trend import determine_trend
import pandas as pd

##TO-DO make sure each process exclusively runs(mutex, locks)
URL = 'https://api.coinmarketcap.com/v2/ticker/?convert=USD&limit=10'


class NMC():
	def __init__(self,config_file,processor):
		self.config_file = config_file
		self.processor = processor
		self.online_data = None
		self.parsed_online_data = None
		self.config = None
		self.load_config()
		self.topic = self.config['topic']
		self.host = self.config.get('host','localhost')
		self._simpleClient=kafka.client.SimpleClient(self.host)
		self.check_topic()	
		self.processing()
		

	def check_topic(self):
		return self._simpleClient.ensure_topic_exists(self.topic)

	def processing(self):
		if self.processor == 'producer':
			self.producer = kafka.KafkaProducer()
			self.fetch_online_data()
			self.parse_online_data()

		elif self.processor == 'consumer':
			self.load_redis()
			print "Consuming Data"
			self.consumer = kafka.KafkaConsumer(self.topic,auto_offset_reset='earliest',consumer_timeout_ms=1000)
			self.fetch_queue_data()

		elif self.processor == 'processor':
			self.load_redis()
		    	self.process_data()	
			#process data
		else:
			print("Missing processor(producer|consumer|processor)")
			sys.exit(1)

	def process_data(self):
		keys = self.redis.keys()
 		import matplotlib.pyplot as plt
		nrows = len(keys)/2 if len(keys)%2==0 else (len(keys)+1)/2
		ncols = 2
		f,ax = plt.subplots(nrows=nrows,ncols=ncols)		
		for idx,key in enumerate(keys):
			prices=[]
			data=self.redis.zrange(key,0,-1)
			x=idx/ncols
			y=idx%ncols
			for record in data:
				record = json.loads(record)
				price = record['quotes']['USD']['price']
				prices.append(price)
			dt = determine_trend(prices,key)
			print(dt.coef)

	def load_config(self):
		print "Loading Configuration File"
		_fp = open(self.config_file, 'r')
		self.config = json.load(_fp)
		_fp.close()

	def fetch_online_data(self):
		print "Getting online data"
		response = requests.get(URL)
		self.online_data = response.json().get('data')

	def parse_online_data(self):
		print "Parsing Data"
		print "Using Topic: %s"%(self.topic)
		map(self.push_data,self.online_data)
		
	def push_data(self,message):
		print "Pushing message: %s"%(self.online_data.get(message))
		_msg = json.dumps(self.online_data.get(message))
		self.producer.send(self.topic,_msg)
		return True

	def load_redis(self):
		self.redis = redis.Redis()
	
	def fetch_queue_data(self):
		print "Fetching Data from Topic"
		print "Using Topic: %s"%(self.topic)
		for records in self.consumer:
			value = json.loads(records.value)
			coin_key = value.get('symbol')
			coin_score = value.get('last_updated')
			print(coin_key,coin_score)
			self.redis.zadd(coin_key,records.value,coin_score)
			
		


if __name__ == '__main__':
    conf, processor = sys.argv[1:]
    NMC(conf, processor)
