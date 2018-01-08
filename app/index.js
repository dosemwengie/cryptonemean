var express=require('express');
var app=express();
var https=require('https');
var mongoose=require('mongoose');
const axios = require('axios');
var cmschema = require('./lib/coinmarketschema.js');
var db = cmschema.db;
var coinmodel = cmschema.coinModel;
//mongoose.connect('mongodb://localhost/coinmarket',{useMongoClient: true});
db.on('error', console.error.bind(console, "DB ERROR"));
//db.on('connected', console.log.bind(console, "SUCCESSFULLY CONNECTED"));
coinURL='https://api.coinmarketcap.com/v1/ticker/?convert=USD&limit=5';
var getData = function(coins){
		(function(coins){
		for(var i=0; i<coins.length; i++){
			console.log(coins[i].id);
			(coinmodel.findOne({id: coins[i].id},function(err,data){
			if (err){
				console.log('err');
			}
			else{
			console.log("Data: "+data);
				}
				})
			)(coins[i]);
			}
			})(coins);
		};
axios.get(coinURL)
	.then(response => {
		console.log("Something");
		var coinData=response.data;
		var coins=coinData;
		x=[];
		x.push(getData(coins));
		Promise.all(x)
		.then(function(){
		})
		.catch(function(){
		});
	
	})
	.catch(error => {
		console.log(err);
	});
