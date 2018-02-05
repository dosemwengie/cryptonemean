var express=require('express');
var app=express();
var https=require('https');
const axios=require('axios');
var MongoClient = require('mongodb').MongoClient;
var dblink = "mongodb://localhost:27017/"
coinURL='https://api.coinmarketcap.com/v1/ticker/?convert=USD&limit=0';
var collection="coinmarket";
var userTable = "UserCoins";
var volumeTable = "volume";
var processData = {};
var mongoConnect = MongoClient.connect(dblink, callback);
var processData  = function(err, database){
	if (err) throw err;
	var db = database.db("localhost");
	axios.get(coinURL)
		.then(function(response) {
			var coins = response.data;
			var getData = function(coin){
				db.collection(collection).updateOne({name:coin.id},{ $set : {
				name:coin.id,
				symbol: coin.symbol,
				rank: coin.rank,
				price_usd: coin.price_usd,
				price_btc: coin.price_btc,
				day_volume_usd: coin['24h_volume.usd'],
				market_cap_usd: coin.market_cap_usd,
				available_supply: coin.available_supply,
				total_supply: coin.total_supply,
				percent_change_1h:coin.total_supply_1h,
				percent_change_24h: coin.percent_change_24h,
				percent_change_7d: coin.percent_change_7d,
				last_updated: coin.last_updated }},
				{ upsert: true }, function(err,res){
				console.log(res.result);
			});
		};
		coins.map(function(coin){
		getData(coin,function(){
			db.collection(userTable).find({},function(err,res){
			console.log(res);
			});
		});
		});
		});
	};
var updateVolume = function(err, database){
	if (err) throw err;
	var db = database.db("localhost");
	db.collection(collection).find({}, function(err,res){
		
		db.collection(volumeTable).updateOne({name: res.name}, {$set: 
			date: res.last_updated,
			volume: res.day_volume_usd
		});
	});
};
