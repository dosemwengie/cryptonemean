var mongoose = require('mongoose');
var mongodb = 'mongodb://localhost/coinmarket';
var _db = mongoose.createConnection(mongodb);
mongoose.Promise = global.Promise;
var coinschema = mongoose.Schema({
id: String,
name: String,
symbol: String,
rank: Number,
price_usd: Number,
price_btc: Number,
day_volume_usd: Number,
market_cap_usd: Number,
available_supply: Number,
total_supply: Number,
max_supply: Number,
percent_change_1h: Number,
percent_change_24h: Number,
percent_change_7d: Number,
last_updated: Number
});

var coinModel = mongoose.model('coinModel', coinschema);


module.exports = {db: _db, coinModel: coinModel};
