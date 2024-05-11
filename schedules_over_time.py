import requests
import pandas as pd
import os
import zipfile
import time

def download_feeds():

    api_key = "yQLFQbjRexIgMYdzs5D0CsU57GXlGAZP"

    headers = {
        'Api-Key': api_key,
    }

    #base url for the API: https://transit.land/api/v2/rest
    base_url = "https://transit.land/api/v2/rest"


    #Victoria onestop ID: 
    one_stop_id = "f-c28-bctransit~victoriaregionaltransitsystem"

    #search feed versions for Victoria - limit is 100
    request = requests.get(base_url + "/feed_versions?feed_key=" + one_stop_id + "&limit=10000", headers=headers)

    #create pandas dataframe from json
    df = pd.DataFrame.from_dict(request.json()['feed_versions'])

    #eliminate anything with an earliest_calendar_date after 2005
    df = df[df['earliest_calendar_date'] > '2005-01-01']
    #eliminate any duplicate earliest_calendar_date
    df = df.drop_duplicates(subset=['earliest_calendar_date'])

    #eliminate anything with a duplicate year and month
    df['year_month'] = df['earliest_calendar_date'].apply(lambda x: str(x)[:7])
    df = df.drop_duplicates(subset=['year_month'])

    #check which ones contain september (any year) using earliest_calendar_date and latest_calendar_date
    df['earliest_calendar_date'] = pd.to_datetime(df['earliest_calendar_date'])
    df['latest_calendar_date'] = pd.to_datetime(df['latest_calendar_date'])
    
    def contains_sept(start_date, end_date):
        if start_date.year == end_date.year:
            if start_date.month <= 9 and end_date.month >= 9:
                return True
        elif start_date.month < 9:
            return True
        
        return False
    
    df['Contains Sept'] = df.apply(lambda x: contains_sept(x['earliest_calendar_date'], x['latest_calendar_date']), axis=1)
        
    df = df[df['Contains Sept'] == True]

    df['Year'] = df['earliest_calendar_date'].apply(lambda x: x.year)
    #remove duplicate years
    df = df.drop_duplicates(subset=['Year'])

    print(df[['earliest_calendar_date', 'latest_calendar_date', 'Year']])

    for sha1 in df['sha1']:
        #request example: GET /api/v2/rest/feed_versions/8f99f69503edfa52e06ec5673e582d3a684c05ca/download
        request = requests.get(base_url + "/feed_versions/" + sha1 + "/download", headers=headers)
        #write to "Historical Feeds" with name 'gtfs-[year].zip'
        with open("Historical Feeds/gtfs-" + str(df[df['sha1'] == sha1]['Year'].iloc[0]) + ".zip", 'wb') as f:
            f.write(request.content)
        
        time.sleep(1)

        #unzip file
        with zipfile.ZipFile("Historical Feeds/gtfs-" + str(df[df['sha1'] == sha1]['Year'].iloc[0]) + ".zip", 'r') as zip_ref:
            zip_ref.extractall("Historical Feeds/gtfs-" + str(df[df['sha1'] == sha1]['Year'].iloc[0]))
        
    #delete all zip files in "Historical Feeds" folder
    for file in os.listdir("Historical Feeds"):
        if file.endswith(".zip"):
            os.remove("Historical Feeds/" + file)
    return

#download_feeds()

def analyze_feeds():
   
    #create df with columns date, route, runtime, headways
    df = pd.DataFrame(columns=['date', 'route', 'runtime', 'headways'])

    for folder in os.listdir("Historical Feeds"):
        print(folder)
        calendar = pd.read_csv("Historical Feeds/" + folder + "/calendar.txt")
        calendar['start_date'] = pd.to_datetime(calendar['start_date'], format='%Y%m%d')
        calendar['end_date'] = pd.to_datetime(calendar['end_date'], format='%Y%m%d')

        calendar = calendar.sort_values(by='start_date')

        calendar = calendar[calendar.monday == 1]

        def contains_september(start_date, end_date):
            if start_date.year == end_date.year:
                if start_date.month <= 9 and end_date.month >= 9:
                    return True
            elif start_date.month < 9:
                return True
            return False
        
        calendar['Contains Sept'] = calendar.apply(lambda x: contains_september(x['start_date'], x['end_date']), axis=1)

        service_id = calendar[calendar['Contains Sept'] == True]['service_id'].iloc[0]
        
        service_date = calendar[calendar['service_id'] == service_id]['start_date'].iloc[0]
        if service_date in df.date:
            print(folder + ": service date already in database")
            continue

        routes = pd.read_csv("Historical Feeds/" + folder + "/routes.txt")
        trips = pd.read_csv("Historical Feeds/" + folder + "/trips.txt")
        stop_times = pd.read_csv("Historical Feeds/" + folder + "/stop_times.txt")
        
        trips = trips[trips['service_id'] == service_id]

        trips = trips.merge(routes[['route_id', 'route_short_name']])

        #select trips that have the following route_short_name: 15, 26, 50, 4, 14
        
        routes_of_interest = [15, 26, 50, 4, 14]

        trips = trips[trips['route_short_name'].isin(routes_of_interest)]

        stop_times = stop_times[stop_times.trip_id.isin(trips.trip_id)]
        
        #remove stop_times that have an arrival time with the first two characters being a 24, 25, or 26
        stop_times = stop_times[~stop_times['arrival_time'].str.startswith(('24', '25', '26'))]
        stop_times = stop_times[~stop_times['departure_time'].str.startswith(('24', '25', '26'))]

        stop_times['arrival_time'] = pd.to_datetime(stop_times['arrival_time'], format='%H:%M:%S')
        stop_times['departure_time'] = pd.to_datetime(stop_times['departure_time'], format='%H:%M:%S')

        #aggregate stop_times by trip_id, get first and last stop times
        stop_times = stop_times.groupby('trip_id').agg({'arrival_time': ['min', 'max'], 'departure_time': 'min'})

        stop_times['runtime'] = stop_times['arrival_time']['max'] - stop_times['arrival_time']['min']

        stop_times = stop_times.sort_values(by=('departure_time','min'))
        stop_times.reset_index(inplace=True)

        stop_times = stop_times[['trip_id', 'runtime', 'departure_time']].reset_index()

        stop_times = stop_times.droplevel(1, axis=1)

        stop_times = stop_times.merge(trips[['trip_id', 'route_short_name']])

        #select trips between 7am and 8am
        stop_times['hour'] = stop_times['departure_time'].dt.hour
        stop_times = stop_times[stop_times['hour'] == 7]
        
        #convert runtime to minutes. Int object
        stop_times['runtime'] = stop_times['runtime'].dt.seconds / 60

        for route in stop_times.route_short_name.unique():

            if route in [4, 14, 15, 26]:
                headsign_keyword = "UVic"
            else:
                headsign_keyword = "Downtown"
            
            trips = trips[trips.trip_headsign.str.contains(headsign_keyword)]
            stop_times = stop_times[stop_times.trip_id.isin(trips.trip_id)]
            
            route_trips = stop_times[stop_times['route_short_name'] == route]
        
            avg_runtime = route_trips['runtime'].mean()
            headways = route_trips['departure_time'].diff().dt.seconds / 60
            
            headways = headways.dropna()
            avg_headway = headways.mean()


            df = pd.concat([df, pd.DataFrame({'date': [service_date], 'route': [route], 'runtime': [avg_runtime], 'headways': [avg_headway]})])    

    #sort df by route and date
    df = df.sort_values(by=['route', 'date'])
    print(df)
    #plot runtimes over time for each route
    import matplotlib.pyplot as plt
    plot, ax = plt.subplots()
    for route in routes_of_interest:
        df[df['route'] == route].plot(x='date', y='runtime', ax=ax, label=route)
    
    plt.show()

analyze_feeds()