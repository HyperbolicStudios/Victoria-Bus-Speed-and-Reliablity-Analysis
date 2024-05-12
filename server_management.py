import os
from inspect import getsourcefile
from os.path import abspath
import pandas as pd
import pymongo
import dns.resolver

dns.resolver.default_resolver=dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers=['8.8.8.8']

client = pymongo.MongoClient(os.environ['MONGO_URL'])
mydb = client.Cluster0
mycol = mydb["transit_speed_data"]

#set active directory to file location
directory = abspath(getsourcefile(lambda:0))

#Downloads bus position/speed logs from YYJ Bus Speed Tracker database
def download_from_mongo():
    #download all data from mongo
    myquery = {}
    mydoc = mycol.find(myquery)
    df = pd.DataFrame(list(mydoc))
    df = df.drop(columns = ["_id"])
    print(df)
    df.to_csv("timeline.csv", index = False)
    return

download_from_mongo()
