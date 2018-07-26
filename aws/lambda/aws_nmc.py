from decimal import Decimal
import boto3
import json
import requests
import os
from datetime import datetime
from binance.client import Client
import logging
from time import sleep

#coin_table=boto3.resource('dynamodb',endpoint_url='http://localhost:8000').Table('coins')
#user_table=boto3.resource('dynamodb',endpoint_url='http://localhost:8000').Table('users')

logging.basicConfig(format='%(asctime)s %(message)s',level=logging.INFO)

user_example = {'preference': {
  'XLM': {'allocation': Decimal('0.25'),
   'desired_action': None,
   'lastOrder': None,
   'lastOrderId': None,
   'buy': Decimal('-0.1'),
   'coin_amount': Decimal('0'),
   'holdings': Decimal('0'),
   'quota': False,
   'sell': Decimal('0.10')},
  'ADA': {'allocation': Decimal('0.25'),
   'desired_action': None,
   'lastOrder': None,
   'lastOrderId': None,
   'buy': Decimal('-0.10'),
   'coin_amount': Decimal('0'),
   'holdings': Decimal('0'),
   'quota': False,
   'sell': Decimal('0.10')}},
 'name': 'Nemean',
 'wallet': Decimal('250.0')}

API_KEY_PARAM = 'bn_api_key'
API_SECRET_PARAM = 'bn_secret_param'
BASE_COIN = 'USDT'
URL = 'https://api.coinmarketcap.com/v2/ticker/?convert=USD&limit=50'
FEE = Decimal('0.001')
THRESHOLD=86400
TRANSACTION_WAIT=10

class NMC():
	def __init__(self):
		self.region=os.environ.get('AWS_REGION')
		self.coin_table,self.user_table = None, None
		self.ssm = boto3.client('ssm')
		self.api_key, self.api_secret = None, None
		self.get_api_s()
		self.client = Client(self.api_key, self.api_secret)
		self.set_db()
		self.fetch_online_data()
		#self.insert_data()
		self.map_user_evaluation()

	def get_api_s(self):
		self.api_key = self.ssm.get_parameter(API_KEY_PARAM, WithDecryption=True)
		self.api_secret = self.ssm.get_parameter(API_SECRET_PARAM, WithDecryption=True)

	def set_db(self):
		if not self.region:
			self.coin_table = boto3.resource('dynamodb',endpoint_url='http://localhost:8000').Table('coins')
			self.user_table = boto3.resource('dynamodb',endpoint_url='http://localhost:8000').Table('users')
		else:
			self.coin_table = boto3.resource('dynamodb').Table('coins')
			self.user_table = boto3.resource('dynamodb').Table('users')
			
	def fetch_online_data(self):
		logging.info("Getting online data @ %s"%(datetime.now()))
		response = requests.get(URL)
		self.online_data = response.json().get('data')

		self.traverse_dictionary()

	def traverse_dictionary(self):
		keys = self.online_data.keys()
		for key in keys:
			new_key = self.online_data[key]['symbol']
			self.online_data[new_key] = self.online_data.pop(key)

			

	def insert_data(self):
		logging.info("Inserting Data into DynamoDB")
		with self.coin_table.batch_writer() as batch:
			for coin in self.online_data:
				if coin not in self.online_data:
					continue		
				data = self.online_data[coin]
				supplies = ['circulating_supply','max_supply','total_supply']
				for supply in supplies:
					if data[supply] is None:
						data[supply] = Decimal('0')
					else:
						data[supply] = Decimal(str(data[supply]))
				item={
					'name':data['name'],
					'last_updated':data['last_updated'],
					'rank':data['rank'],
					'symbol':data['symbol'],
					'quotes':data['quotes'],
					'circulating_supply':data['circulating_supply'],
					'id':data['id'],
					'max_supply':data['max_supply'],
					'total_supply':data['total_supply'],
					'website_slug':data['website_slug'],
					'expiration':data['last_updated']+THRESHOLD
				}
				for numericals in item['quotes']['USD']:
					if item['quotes']['USD'][numericals] is None:
						item['quotes']['USD'][numericals] = Decimal('0')
					else:
					 item['quotes']['USD'][numericals] = Decimal(str(item['quotes']['USD'][numericals]))

				batch.put_item(
					Item=item
		)
	def map_user_evaluation(self):
		response = self.user_table.scan()
		users = response['Items']
		map(self.data_evaluation,users)

	def data_evaluation(self,user_data):
		logging.info("User: %s"%(user_data['name']))
		for coin in user_data['preference']:
			logging.info("Checking coin: %s"%(coin))
			coin_data = user_data['preference'][coin]
			can_sell, can_buy = False, False
			current_price = self.online_data[coin]['quotes']['USD']['price']
			current_price = Decimal(current_price)
			percentages = [ self.online_data[coin]['quotes']['USD'][x] for x in self.online_data[coin]['quotes']['USD'] if x.startswith('percent_change')]
			buy_percentage = coin_data['buy']*100
			sell_percentage = coin_data['sell']*100
			logging.info("Percentages: %s"%(percentages))
			logging.info(coin_data)
			if coin_data['coin_amount'] == 0:
				if buy_percentage >= min(percentages):
					can_buy = True
			else:
				worth_per_coin = coin_data['coin_amount']/coin_data['holdings']
				desired_action = user_data['preference'][coin]['desired_action']
				if (current_price - worth_per_coin)/100 <= buy_percentage and desired_action == 'buy':
					can_buy = True
				elif (current_price - worth_per_coin)/100 >= sell_percentage and desired_action == 'sell':
					can_sell = True 
			
			logging.info("Before Wallet %s"%(user_data['wallet']))
			if can_buy:
				self.do_transaction(coin,user_data,current_price,action='buy')
			if can_sell:
				self.do_transaction(coin,user_data,current_price,action='sell')
		logging.info(user_data)
		self.user_table.put_item(Item=user_data)
		print

	def get_balance(self, coin=None):
		account = self.client.get_account()		
		if coin is None:		
			balances = [x for x in account['balances'] if float(x['free']) > 0]
		else:
			balances = [x for x in account['balances'] if float(x['free']) > 0 and x['asset'] == coin]
		balance = 0
		for ticker in balances:
			symbol = ticker['asset']
			amount = float(ticker['free'])
			current_price = self.client.get_symbol_ticker(symbol=''.join([symbol,BASE_COIN]))
			current_price = current_price.get('price')
			balance += current_price*amount
		return balance

	def get_wallet(self, asset=None):
		if asset is None:
			asset=BASE_COIN
		balance = self.client.get_asset_balance(asset=asset)
		balance = balance.get('free')
		return Decimal(balance)

	def getOrderStatus(self,coin,user_data,orderId=None):
		if orderId is None:
			orderId = user_data['preference'][coin]['lastOrderId']
		symbol = ''.join([coin, BASE_COIN])
		result = self.client.get_order(symbol=symbol, orderId=orderId)
		status = result['status']
		logging.info("Coin: %s, status: %s"%(coin,status))
		return status == 'FILLED'

	def do_transaction(self,coin,user_data,current_price,action=None):
		wallet = self.get_wallet()
		allocation = user_data['preference'][coin]['allocation']
		coin_amount = user_data['preference'][coin]['coin_amount']
		quota = user_data['preference'][coin]['quota']
		holdings = user_data['preference'][coin]['holdings']
		desired_price = self.online_data[coin]['quotes']['USD']['price']
		symbol = ''.join([coin, BASE_COIN])
		if quota and action == 'buy':
			logging.info("Quota reached!")
			return
		last_status = self.getOrderStatus(coin,user_data)
		
		if not last_status:
			logging.info("Coin latest status not filled")
			return
 
		if user_data['preference'][coin]['lastOrder'] == 'PENDING':
			user_data['preference'][coin]['lastOrder'] = 'FILLED'
			user_data['preference'][coin]['coin_amount'] = self.get_wallet(asset=coin)
			user_data['preference'][coin]['holdings'] = self.get_balance(coin=coin)
			

		if action == 'buy':
			limit = Decimal(allocation * wallet)
			wallet_factor = -1
			holding_coin_factor = 1
			user_data['preference'][coin]['quota'] = True
			user_data['preference'][coin]['desired_action']='sell'
			
			

		elif action == 'sell':
			limit = Decimal(current_price * coin_amount)
			wallet_factor = 1
			holding_coin_factor = -1
			user_data['preference'][coin]['quota'] = False
			user_data['preference'][coin]['desired_action']='buy'

		else:
			raise Exception('action needed')

		fee = limit * FEE
		real_limit = limit - fee
		new_coins = real_limit/current_price
		try:
			transaction_call = self.client.create_order(symbol=symbol,side=action,type='TAKE_PROFIT',quantity=new_coins,price=desired_price)
			orderId = transaction_call['RESULT']['orderId']
			sleep(TRANSACTION_WAIT)
		except Exception as e:
			logging.error("Could not place order: %s"%(str(e)))
			return False

		user_data['wallet'] = self.get_wallet()
		transaction_status = self.getOrderStatus(coin,user_data,orderId=orderId)
		user_data['preference'][coin]['lastOrderId'] = orderId
		user_data['preference'][coin]['lastOrder'] = 'PENDING' if not transaction_status else 'FILLED'
		user_data['preference'][coin]['coin_amount'] = self.get_wallet(asset=coin)
		user_data['preference'][coin]['holdings']  = self.get_balance(coin=coin)
		logging.info("User %s, is %sing %s worth of %s"%(user_data["name"],action,desired_price*new_coins,coin))
		logging.info("After transaction, wallet is now %s"%(user_data['wallet']))
		logging.info("Holdings %s\nCoin Amount %s"%(user_data['preference'][coin]['holdings'],user_data['preference'][coin]['coin_amount']))

def handler(event, context):
	_=NMC()


