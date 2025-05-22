import requests
import pandas as pd
import os
import zipfile
import time
import geopandas as gpd
from shapely.geometry import LineString

import plotly.colors as pc
import plotly.express as px
import plotly.graph_objects as go

#take shapes.txt df, add segments together, and compute length in meters
def aggregate_shapes(shapes):
    #create geopandas dataframe from shapes. use shape_pt_lon,shape_pt_lat
    #create line objects from shape_pt_lon, shape_pt_lat    
    gdf = gpd.GeoDataFrame(shapes, geometry=gpd.points_from_xy(shapes['shape_pt_lon'], shapes['shape_pt_lat']))
    lines = gpd.GeoDataFrame()

    #create line objects from points
    for shape_id in gdf.shape_id.unique():
        points = gdf[gdf['shape_id'] == shape_id]

        #create a single linestring from the points
        line = LineString(points.geometry)
        lines = pd.concat([lines, pd.DataFrame({'shape_id': [shape_id], 'geometry': [line]})], ignore_index=True)
    
    lines = lines[['shape_id', 'geometry']]
    lines = gpd.GeoDataFrame(lines, geometry='geometry').set_crs(epsg=4326).to_crs(epsg=26910)
    lines['length'] = lines.geometry.length
    lines = lines.to_crs(epsg=4326)

    #sort by shape_id
    lines = lines.sort_values(by='shape_id')    
    lines = lines.reset_index(drop=True)
    return lines

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

    print(df)
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
    
    def contains_desired_date(start_date, end_date):
            #target date: sept 20 (arbitrary) of whatever year start_date is in
            print(start_date, end_date)
            target_date = pd.to_datetime(str(start_date.year) + "-09-20")

            if start_date <= target_date and end_date >= target_date:
                return True
            return False
    
    df['Contains Date'] = df.apply(lambda x: contains_desired_date(x['earliest_calendar_date'], x['latest_calendar_date']), axis=1)
        
    df = df[df['Contains Date'] == True]

    df['Year'] = df['earliest_calendar_date'].apply(lambda x: x.year)
    #remove duplicate years
    df = df.drop_duplicates(subset=['Year'])

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

def analyze_feeds():
   
    #create df with columns date, route, runtime, headways
    main_df = pd.DataFrame(columns=['date', 'route_short_name', 'departure_time', 'runtime', 'speed'])

    for folder in os.listdir("Historical Feeds"):
    #for folder in ['gtfs-2024']:
        print(folder)
        calendar = pd.read_csv("Historical Feeds/" + folder + "/calendar.txt")
        calendar['start_date'] = pd.to_datetime(calendar['start_date'], format='%Y%m%d')
        calendar['end_date'] = pd.to_datetime(calendar['end_date'], format='%Y%m%d')

        calendar = calendar.sort_values(by='start_date')

        calendar = calendar[calendar.monday == 1]

        def contains_desired_date(start_date, end_date):
            #target date: sept 20 (arbitrary) of whatever year start_date is in
            target_date = pd.to_datetime(str(start_date.year) + "-09-20")
            if start_date <= target_date and end_date >= target_date:
                return True
            return False
        
        calendar['Contains Sept'] = calendar.apply(lambda x: contains_desired_date(x['start_date'], x['end_date']), axis=1)

        service_ids = calendar[calendar['Contains Sept'] == True]
        service_date = service_ids['start_date'].iloc[0]

        if service_date in main_df.date:
            print(folder + ": service date already in database")
            continue

        routes = pd.read_csv("Historical Feeds/" + folder + "/routes.txt")
        trips = pd.read_csv("Historical Feeds/" + folder + "/trips.txt")
        stop_times = pd.read_csv("Historical Feeds/" + folder + "/stop_times.txt")
        shapes = pd.read_csv("Historical Feeds/" + folder + "/shapes.txt")
        shapes = aggregate_shapes(shapes)
        
        trips = trips[trips['service_id'].isin(service_ids.service_id)]

        trips = trips.merge(routes[['route_id', 'route_short_name']])

        #select trips and associated stop_times with the following route_short_name: 15, 26, 50, 4, 14
        routes_of_interest = [15, 26, 50, 4, 14]
        trips = trips[trips['route_short_name'].isin(routes_of_interest)]
        stop_times = stop_times[stop_times.trip_id.isin(trips.trip_id)]
        
        # Find trip_ids where any stop_time has arrival_time or departure_time starting with 24, 25, or 26
        mask = stop_times['arrival_time'].str.startswith(('24', '25', '26')) | stop_times['departure_time'].str.startswith(('24', '25', '26'))
        bad_trip_ids = stop_times.loc[mask, 'trip_id'].unique()
        # Remove all stop_times for those trip_ids
        stop_times = stop_times[~stop_times['trip_id'].isin(bad_trip_ids)]

        stop_times['arrival_time'] = pd.to_datetime(stop_times['arrival_time'], format='%H:%M:%S')
        stop_times['departure_time'] = pd.to_datetime(stop_times['departure_time'], format='%H:%M:%S')

        #aggregate stop_times by trip_id, get first and last stop times. Calculate runtime
        stop_times = stop_times.groupby('trip_id').agg({'arrival_time': ['min', 'max'], 'departure_time': 'min'})
        stop_times['runtime'] = stop_times['arrival_time']['max'] - stop_times['arrival_time']['min']

        stop_times = stop_times.sort_values(by=('departure_time','min'))
        stop_times.reset_index(inplace=True)
        stop_times = stop_times[['trip_id', 'runtime', 'departure_time']].reset_index()
        stop_times = stop_times.droplevel(1, axis=1)

        #add route_short_name and shape_id to stop_times
        stop_times = stop_times.merge(trips[['trip_id', 'route_short_name', 'shape_id']])
        
        #convert runtime to minutes. Int object
        stop_times['runtime'] = stop_times['runtime'].dt.seconds / 60
        
        #select a specific, consistent direction for the analysis.
        for route in stop_times.route_short_name.unique():
            if route in [4, 14, 15, 26]:
                headsign_keyword = "UVic"
            else:
                headsign_keyword = "Downtown"
            
            #filter stop_times by route number and headsign_keyword
            route_stop_times = stop_times[stop_times['route_short_name'] == route]
            relevant_trips = trips[trips['trip_headsign'].str.contains(headsign_keyword)]
            route_stop_times = route_stop_times[route_stop_times['trip_id'].isin(relevant_trips.trip_id)]

            #merge with shapes
            route_stop_times = route_stop_times.merge(shapes[['shape_id', 'length']], on='shape_id')

            #create a pivot table summarizing the mean length for each route
            pivot = route_stop_times.pivot_table(index='route_short_name', values='length', aggfunc='mean')
            
            #print(len(route_stop_times), "trips for route", route, "on", service_date)
            #Filter out short turn trips. Filter out any trip with a below-average length
            route_stop_times = route_stop_times[route_stop_times['length'] > 0.75*pivot.loc[route]['length']]
            #print(len(route_stop_times), "trips for route", route, "on", service_date, "after filtering")
            #calculate speed in km/h
            route_stop_times['speed'] = (route_stop_times['length']/1000) / (route_stop_times['runtime'] / 60)

            #append data to the main dataframe. Add the folder name, service_date, the route, headsign, departure time, and runtime
            route_stop_times['date'] = service_date
          
            main_df = pd.concat([main_df, route_stop_times[['date', 'route_short_name', 'departure_time', 'runtime', 'speed']]], ignore_index=True)

    #CREATE GRAPHS
    df = main_df.copy()
    df.date = df.date.dt.year
    scale = px.colors.diverging.RdYlBu_r

    n = len(df.date.unique())
    colours = pc.sample_colorscale(scale, n)

    routes = sorted(df.route_short_name.unique())
    years = sorted(df.date.unique())

    for i in range(0, len(routes)):
        route = routes[i]
        fig = go.Figure()

        for j in range(0, len(years)):
            date = years[j]
            series = df[(df.route_short_name == route) & (df.date == date)]

            #fade main_colour by an increment (older date -> more grey)
            colour = colours[j]

            #add line and plot departure_time vs speed. no marker
            fig.add_trace(go.Scatter(x=series.departure_time, y=series.runtime, mode='lines', name=str(date), line=dict(color=colour)))

        #add title
        fig.update_layout(
            title="End-to-end runtimes over time: route " + str(route),
            title_x=0.5
        )

        #add interactive legend on the right
        fig.update_layout(
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        fig.write_html('docs/plots/historical_runtimes/runtimes route ' + str(route) + '.html')
    
    return
#download_feeds()
analyze_feeds()