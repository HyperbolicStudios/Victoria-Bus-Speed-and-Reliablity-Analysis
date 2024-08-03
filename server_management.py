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
    
    df.to_csv("timeline.csv", index = False)

    #convert Time column (in epoch time) to human-readable time
    df['Time'] = pd.to_datetime(df['Time'], unit='s')
    #convert to pst
    df['Time'] = df['Time'].dt.tz_localize('UTC').dt.tz_convert('America/Los_Angeles')
    print("Data downloaded from MongoDB. {} points. Time range: {} to {}".format(len(df), df['Time'].min(), df['Time'].max()))

    return

download_from_mongo()

def summarize_data():
    df = pd.read_csv("timeline.csv")
    #summarize the first date and the last date
    df['Time'] = pd.to_datetime(df['Time'], unit='s')
    #pst
    df['Time'] = df['Time'].dt.tz_localize('UTC').dt.tz_convert('America/Los_Angeles')
    print("First date: ", df['Time'].min())
    print("Last date: ", df['Time'].max())
    return

summarize_data()

