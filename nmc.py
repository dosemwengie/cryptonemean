import json
import sys
import requests
from optparse import OptionParser
import redis
import kafka
from functools import partial


##TO-DO make sure each process exclusively runs(mutex, locks)
URL='https://api.coinmarketcap.com/v2/ticker/?convert=USD&limit=10'

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
			self.consumer = kafka.KafkaConsumer(self.topic)
			self.fetch_queue_data()
		elif self.processor == 'processor':
			self.load_redis()
			#process data
		else:
			print("Missing processor(producer|consumer)")
			sys.exit(1)

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
		_msg = json.dumps(message)
		self.producer.send(self.topic,_msg)
		return True

	def load_redis(self):
		self.redis = redis.Redis()
	
	def fetch_queue_data(self):
		print "Fetching Data from Topic"
		print "Using Topic: %s"%(self.topic)
		records=self.consumer.poll(timeout_ms=0)
		print(records)
		


if __name__ == '__main__':
	conf,processor = sys.argv[1:]
	NMC(conf,processor)


