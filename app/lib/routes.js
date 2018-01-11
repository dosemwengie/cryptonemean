var addData = function(data){
db.collection(UserCoins).insert({
    coin:data.symbol,
    user: data.user,
    p_l: data.p_l,
    stop_loss:data.stop_loss,
    entry: data.entry,
    exit: data.exit,
    current: data.current
            },function(err,data){
            if (err){
            throw(err);
            }
            });
       
var modifyData = function(data){
db.collection(UserCoins).update({_id:data._id},{
    coin:data.symbol,
    user: data.user,
    p_l: data.p_l,
    stop_loss:data.stop_loss,
    entry: data.entry,
    exit: data.exit,
    current: data.current
}, function(err,data){
    if (err){
    throw(err);
    }
});
var removeData = function(data){
db.collection(UserCoins).remove({_id:data._id},function(err,data){
if (err){
throw(err);
}
});

