from decimal import *
import boto3
import json
import requests
import os
from datetime import datetime
from binance.client import Client
import logging
from time import sleep

getcontext().prec = 7

root = logging.getLogger()
if root.handlers:
    for handler in root.handlers:
        root.removeHandler(handler)
logging.basicConfig(format='%(asctime)s %(message)s',level=logging.INFO)

user_example = {'preference': {
  'XLM': {'allocation': Decimal('0.25'),
   'desired_action': None,
   'lastOrder': None,
   'lastOrderId': None,
   'lastPrice': None,
   'buy': Decimal('-0.1'),
   'coin_amount': Decimal('0'),
   'holdings': Decimal('0'),
   'quota': False,
   'sell': Decimal('0.10')},
  'ADA': {'allocation': Decimal('0.25'),
   'desired_action': None,
   'lastOrder': None,
   'lastOrderId': None,
   'lastPrice': None,
   'buy': Decimal('-0.10'),
   'coin_amount': Decimal('0'),
   'holdings': Decimal('0'),
   'quota': False,
   'sell': Decimal('0.10')}},
 'name': 'Nemean',
 'wallet': Decimal('250.0')}

API_KEY_PARAM = 'bn_api_key'
API_SECRET_PARAM = 'bn_secret_key'
BASE_COIN = 'USDT'
URL = 'https://api.coinmarketcap.com/v2/ticker/?convert=USD&limit=50'
FEE = Decimal('0.001')
THRESHOLD=86400
TRANSACTION_WAIT=10
BN_TRANSLATE = {
'IOTA':'MIOTA'
}
ERROR_CHANNEL = 'error_channel'

class NMC():
	def __init__(self):
		self.region=os.environ.get('AWS_REGION')
		self.coin_table,self.user_table = None, None
		self.client = None
		self.ssm = boto3.client('ssm')
		self.set_db()
		self.set_error_channel()
		self.fetch_online_data()
		self.map_user_evaluation()
		

	def get_api_s(self,user):
		user_api_key = '_'.join([user,API_KEY_PARAM])
		user_secret_key = '_'.join([user,API_SECRET_PARAM])
		api_key = self.ssm.get_parameter(Name=user_api_key, WithDecryption=True)['Parameter']['Value']
		api_secret = self.ssm.get_parameter(Name=user_secret_key, WithDecryption=True)['Parameter']['Value']
		return (api_key,api_secret)

	def get_slack(self,user):
		user_channel = '_'.join([user,'slack_channel'])
		response = self.ssm.get_parameter(Name=user_channel, WithDecryption=True)['Parameter']['Value']
		return response

	def set_error_channel(self):
		response = self.ssm.get_parameter(Name=ERROR_CHANNEL, WithDecryption=True)['Parameter']['Value']
		self.error_channel = response


	def set_db(self):
		if not self.region:
			logging.info("Using local db")
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
		user = user_data['name']
		api_key,secret_key = self.get_api_s(user)
		self.client = Client(api_key, secret_key)
		user_data['wallet'] = self.get_wallet()
		self.user_channel = self.get_slack(user)
		logging.info("User: %s"%(user_data['name']))
		for coin in user_data['preference']:
			coin_data = user_data['preference'][coin]
			can_sell, can_buy = False, False
			translated_coin = BN_TRANSLATE.get(coin,coin)
			current_price = self.online_data[translated_coin]['quotes']['USD']['price']
			current_price = Decimal(current_price) * Decimal(1)
			print("%s: Current Price: %s"%(coin,current_price))
			percentages = [ self.online_data[translated_coin]['quotes']['USD'][x] for x in self.online_data[translated_coin]['quotes']['USD'] if x.startswith('percent_change')]
			user_data['preference'][coin]['coin_amount'] = self.get_wallet(asset=coin)
			user_data['preference'][coin]['holdings'] = self.get_balance(coin=coin)
			buy_percentage = coin_data['buy']*100
			sell_percentage = coin_data['sell']*100
			print("%s: Percentages: %s"%(coin,percentages))
			if coin_data['coin_amount'] == 0:
				if buy_percentage >= min(percentages):
					can_buy = True
			else:
				worth_per_coin = coin_data['lastPrice']		
				desired_action = user_data['preference'][coin]['desired_action']
				print("%s: Current_price: %s worth_per_coin: %s\n%s: Ratio: %s%% %s?"%(coin,current_price,worth_per_coin,coin,((current_price-worth_per_coin)/worth_per_coin)*100,desired_action))
				if (current_price - worth_per_coin)/worth_per_coin <= buy_percentage and desired_action == 'buy':
					can_buy = True
				elif (current_price - worth_per_coin)/worth_per_coin >= sell_percentage and desired_action == 'sell':
					can_sell = True 
			
			#logging.info("Before Wallet %s"%(user_data['wallet']))
			if can_buy:
				self.do_transaction(coin,user_data,current_price,action='BUY')
			if can_sell:
				self.do_transaction(coin,user_data,current_price,action='SELL')
		print(user_data)
		net_worth_msg = "\nNet Worth: %s"%(self.get_balance())
		print(net_worth_msg)
		self.reset_client()
		self.reset_slack()
		self.user_table.put_item(Item=user_data)

	def get_balance(self, coin=None):
		account = self.client.get_account()		
		if coin is None:		
			balances = [x for x in account['balances'] if float(x['free']) > 0 ]
		else:
			balances = [x for x in account['balances'] if float(x['free']) > 0 and x['asset'] == coin]
		balance = 0
		for ticker in balances:
			symbol = ticker['asset'] if ticker['asset'] != BASE_COIN else 'TUSD'
			amount = float(ticker['free'])
			current_price = self.client.get_symbol_ticker(symbol=''.join([symbol,BASE_COIN]))
			current_price = float(current_price.get('price'))
			balance += current_price*amount
		return Decimal(balance) * Decimal(1)

	def get_wallet(self, asset=None):
		if asset is None:
			asset=BASE_COIN
		balance = self.client.get_asset_balance(asset=asset)
		balance = balance.get('free')
		return Decimal(balance)

	def getOrderStatus(self,coin,user_data,orderId=None):
		if orderId is None:
			orderId = user_data['preference'][coin]['lastOrderId']
			if orderId is None:
				return True
		symbol = ''.join([coin, BASE_COIN])
		result = self.client.get_order(symbol=symbol, orderId=orderId)
		status = result['status']
		print("Coin: %s, status: %s"%(coin,status))
		return status == 'FILLED' 
	
	def reset_client(self):
		self.client = None

	def reset_slack(self):
		self.user_channel = None

	def do_transaction(self,coin,user_data,current_price,action=None):
		wallet = self.get_wallet()
		allocation = user_data['preference'][coin]['allocation']
		coin_amount = user_data['preference'][coin]['coin_amount']
		quota = user_data['preference'][coin]['quota']
		holdings = user_data['preference'][coin]['holdings']
		symbol = ''.join([coin, BASE_COIN])
		if quota and action == 'BUY':
			logging.info("Quota reached!")
			return
		last_status = self.getOrderStatus(coin,user_data)
		
		if not last_status:
			logging.info("Coin latest status not filled")
			return
 
		if user_data['preference'][coin]['lastOrder'] == 'PENDING':
			user_data['preference'][coin]['lastOrder'] = 'FILLED'
			

		if action == 'BUY':
			limit = Decimal(allocation * wallet)
			user_data['preference'][coin]['quota'] = True
			user_data['preference'][coin]['desired_action']='sell'
			message = "Purchased: $"
			
			

		elif action == 'SELL':
			limit = Decimal(current_price * coin_amount)
			user_data['preference'][coin]['quota'] = False
			user_data['preference'][coin]['desired_action']='buy'
			message = "Profit: $"

		else:
			raise Exception('action needed')

		fee = limit * FEE
		real_limit = limit - fee
		new_coins = real_limit/current_price
		symbol_info = self.client.get_symbol_info(symbol=symbol)
		price_filter = [x for x in symbol_info['filters'] if x['filterType']=='PRICE_FILTER'][0]
		tickSize = Decimal(price_filter['tickSize'])
		lot_size_filter = [x for x in symbol_info['filters'] if x['filterType']=='LOT_SIZE'][0]
		lotSize = Decimal(lot_size_filter['stepSize'])
		price = closestNumber(current_price,tickSize)
		quantity = closestNumber(new_coins, lotSize)
		try:
			print("\nsymbol:%s\nside:%s\nquantity:%s\nprice:%s\n"%(symbol,action,new_coins,price))
			transaction_call = self.client.create_order(symbol=symbol,side=action,type='LIMIT',quantity=quantity,price=price,timeInForce='GTC')
			orderId = transaction_call['orderId']
			sleep(TRANSACTION_WAIT)
		except Exception as e:
			err_msg="Could not place order: %s"%(str(e))
			user_data['preference'][coin]['quota'] = not user_data['preference'][coin]['quota']
			user_data['preference'][coin]['desired_action']='buy' if user_data['preference'][coin]['desired_action']=='sell' else 'sell'
			print(err_msg)
			payload = {'text': err_msg}
			requests.post(self.error_channel, data=json.dumps(payload))
			return False
		combined_msg = "%s: %s%s\nNet Worth: %s"%(coin,message,price*quantity,self.get_balance())
		print(combined_msg)
		payload = {'text': combined_msg}
		requests.post(self.user_channel, data=json.dumps(payload))
		user_data['wallet'] = self.get_wallet()
		transaction_status = self.getOrderStatus(coin,user_data,orderId=orderId)
		user_data['preference'][coin]['lastOrderId'] = orderId
		user_data['preference'][coin]['lastOrder'] = 'PENDING' if not transaction_status else 'FILLED'
		user_data['preference'][coin]['coin_amount'] = self.get_wallet(asset=coin)
		user_data['preference'][coin]['holdings']  = self.get_balance(coin=coin)
		user_data['preference'][coin]['lastPrice'] = price
		print("User %s, is %sing %s worth of %s"%(user_data["name"],action,price*quantity,coin))
		print("After transaction, wallet is now %s"%(user_data['wallet']))
		print("Holdings %s\nCoin Amount %s"%(user_data['preference'][coin]['holdings'],user_data['preference'][coin]['coin_amount']))
		

def handler(event, context):
	_=NMC()

def closestNumber(n, m) :
    # Find the quotient
    q = n // m
     
    # 1st possible closest number
    n1 = m * q
     
    # 2nd possible closest number
    if((n * m) > 0) :
        n2 = (m * (q + 1)) 
    else :
        n2 = (m * (q - 1))
     
    # if true, then n1 is the required closest number
    if (abs(n - n1) < abs(n - n2)) :
        return n1
     
    # else n2 is the required closest number 
    return n2


