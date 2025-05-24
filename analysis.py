import os
import geopandas as gpd
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from create_shapes import generate_lines
import plotly.express as px
import plotly.graph_objects as go
import statsmodels.api as sm
import keplergl
import json

from download_from_mongodb import get_headers_df

#Retrieve the entire timeline (as points). Used for the system and corridor maps
def retrieve_timeline(file_limit = 1):
    timeline = pd.DataFrame()
    #for csv file in historical speed data/data:
    files = os.listdir("historical speed data/data")
    file_number = 0
    while(file_number < file_limit):
        filename = files[file_number]
        file_number += 1
        if filename.endswith(".csv"):
            #read csv file
            file = pd.read_csv("historical speed data/data/" + filename, dtype={"Time": np.int64, "Route": str, "Header": np.int64, "Trip ID": np.int64, "Speed": np.float64, "x": np.float64, "y": np.float64, "Occupancy Status": np.int64})
            #append to timeline
            timeline = pd.concat([timeline, file], ignore_index=True)

    #turn into geopandas dataframe based on x and y
    timeline = gpd.GeoDataFrame(timeline, geometry=gpd.points_from_xy(timeline.x, timeline.y))
    timeline = timeline.set_crs("EPSG:4326").to_crs("EPSG:26910")

    #turn 'Time' into Datetime column
    timeline['Datetime'] = pd.to_datetime(timeline['Time'], unit='s', utc=True)
    #convert to PST
    timeline['Datetime'] = timeline['Datetime'].dt.tz_convert('America/Los_Angeles')

    return(timeline)

#Produce a summary of each trip-in-time (i.e. trip X on day Y), with average speed, runtime, etc.
#Used for the runtimes by time and runtimes by date plots
def summarize_trip_data():
    timeline = retrieve_timeline()

    #remove rows with a speed of 0 - speeds up processing and we don't want start/end iddling datapoints
    timeline = timeline[timeline.Speed != 0]

    #Create a new date column, in the format YYYY-MM-DD
    timeline['Date'] = timeline.Datetime.dt.date
   
    #create a new custom_id column, which is the concatenation of the date and trip_id
    timeline['custom_id'] = timeline['Date'].astype(str) + timeline['Trip ID'].astype(str)

    #aggregate by custom_id, taking the difference between the first and last timestamp. This is the runtime
    runtimes_df = timeline.groupby(["custom_id"]).agg({"Time": ["min", "max"], 'Date': 'first', 'Route': 'first', 'Header': 'first'}).reset_index()

    runtimes_df['runtime'] = (runtimes_df['Time']['max'] - runtimes_df['Time']['min'])/60

    #turn two dimensional column names into one dimensional. Just the first element
    runtimes_df.columns = runtimes_df.columns.get_level_values(0)

    #rename the columns
    runtimes_df.columns = ['custom_id', 'Time_min', 'Time_max', 'Date', 'Route', 'Header', 'runtime']

    #remove anything with runtime greater than 200 minutes (extreme outliers) or under 5 minutes
    runtimes_df = runtimes_df[(runtimes_df.runtime < 200) & (runtimes_df.runtime > 5)]

    #Create label with time_min. This is the time in epoch time
    runtimes_df['label'] = pd.to_datetime(runtimes_df['Time_min'], unit='s', utc=True)
    #convert to PST
    runtimes_df['label'] = runtimes_df['label'].dt.tz_convert('America/Los_Angeles').dt.strftime('%Y-%m-%d %H:%M:%S')

    #Headers are stored in a separate collection. Merge the headers with the runtimes_df
    headers = get_headers_df()
    runtimes_df = runtimes_df.rename(columns={"Header": "Header_ID"})

    runtimes_df['Header_ID'] = runtimes_df['Header_ID']
    headers['Header_ID'] = headers['Header_ID']

    runtimes_df = runtimes_df.merge(headers, on="Header_ID", how="left")
    runtimes_df = runtimes_df.drop(columns=["Header_ID", "_id"])

    return(runtimes_df)

def system_map():
    route_segments = generate_lines()
    timeline = retrieve_timeline()
 
    #create a buffer around each line in lines, and create a new geodataframe with the buffers
    route_segments['line_geom'] = route_segments['geometry']
    route_segments['geometry'] = route_segments.buffer(20, cap_style=2)
    route_segments['buffer_id'] = route_segments.index
    timeline['Hour'] = timeline.Datetime.dt.hour

    #spatial merge. Find all the points that are within buffers, and retain buffer geometry.
    timeline = gpd.sjoin(route_segments, timeline, how="left", predicate="intersects")
    
    timeline['geometry'] = timeline['line_geom']
    timeline = timeline[["Hour", "Speed", "buffer_id", "geometry"]]

    #aggregate data and create maps with kepler.gl
    
    #system speed map
    gdf = timeline.groupby(["buffer_id"]).agg({"Speed": "mean", "geometry": "first"}).reset_index()
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:26910")
    gdf = gdf.to_crs("WGS-84")
    gdf['Speed Data'] = gdf['Speed'].round(1)
    gdf['colour'] = np.where(gdf['Speed Data'] > 50, 50, gdf['Speed Data'])
    gdf['Speed'] = gdf['Speed Data'].astype(str) + " km/h"
    
    kepler_config = json.load(open("kepler_configs/speed_map.json"))
    map_1 = keplergl.KeplerGl(height=500, data={"Speed": gdf}, config=kepler_config)
    map_1.save_to_html(file_name="docs/plots/system_speed_map.html", config=kepler_config, read_only=True)
        
    #system peak sped map
    #restrict to between 8am and 11am
    gdf = timeline[(timeline.Hour == 8) | (timeline.Hour == 9) | (timeline.Hour == 10)]
    gdf = gdf.groupby(["buffer_id"]).agg({"Speed": "mean", "geometry": "first"}).reset_index()
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:26910")
    gdf = gdf.to_crs("WGS-84")
    gdf['Speed Data'] = gdf['Speed'].round(1)
    gdf['colour'] = np.where(gdf['Speed Data'] > 50, 50, gdf['Speed Data'])
    gdf['Speed'] = gdf['Speed Data'].astype(str) + " km/h"
    
    kepler_config = json.load(open("kepler_configs/speed_map.json"))
    map_1 = keplergl.KeplerGl(height=500, data={"Speed": gdf}, config=kepler_config)
    map_1.save_to_html(file_name="docs/plots/system_speed_peak_map.html", config=kepler_config, read_only=True)

    #system peak vs off-peak speed map

    gdf = timeline.pivot_table(index=["buffer_id"], columns="Hour", values="Speed", aggfunc="mean").reset_index()
    gdf = gdf.merge(timeline[["buffer_id", "geometry"]].drop_duplicates(subset=["buffer_id"]), on="buffer_id", how="left")
    #calculate a three-hour-window moving average to identify the peak and off-peak speeds
    for i in range(1, 22): #centres of the different windows
        gdf["{}-{}-{}".format(i-1, i, i+1)] = gdf[[i-1, i, i+1]].mean(axis=1)
    #for each row, identify the highest and lowest values of these windows
    cols_to_analyze = gdf.loc[:, "0-1-2":"20-21-22"]
    gdf['Peak'] = cols_to_analyze.min(axis=1).round(1)
    gdf['Peak Hour'] = cols_to_analyze.idxmin(axis=1)
    gdf['Off-Peak'] = cols_to_analyze.max(axis=1).round(1)
    gdf['Off-Peak Hour'] = cols_to_analyze.idxmax(axis=1)

    gdf['Speed Delta'] = gdf['Off-Peak'] - gdf['Peak']

    gdf = gdf[["buffer_id", "geometry", "Peak", "Peak Hour", "Off-Peak", "Off-Peak Hour", "Speed Delta"]]
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:26910")
    gdf = gdf.to_crs("WGS-84")
    gdf['Speed Data'] = gdf['Speed Delta'].round(1)
    gdf['colour'] = np.where(gdf['Speed Data'] > 50, 50, gdf['Speed Data'])
    gdf['Speed Delta'] = gdf['Speed Data'].astype(str) + " km/h"
    
    kepler_config = json.load(open("kepler_configs/delta_map.json"))
    map_1 = keplergl.KeplerGl(height=500, data={"Speed Delta": gdf}, config=kepler_config)
    map_1.save_to_html(file_name="docs/plots/system_delta_map.html", config=kepler_config, read_only=True)
        
    return

def dot_map():
    gdf = retrieve_timeline()
    if len(gdf) >= 150000:
        gdf = gdf.sample(n=150000)

    gdf['Datetime'] = gdf['Datetime'].dt.strftime('%Y-%m-%d %H:%M:%S').astype(str)

    #round speed to 1 decimal place
    gdf.Speed = gdf.Speed.round(1)

    gdf['Speed Data'] = gdf['Speed'].round(1)
    gdf['colour'] = np.where(gdf['Speed Data'] > 35, 35, gdf['Speed Data'])
    gdf['Speed'] = gdf['Speed Data'].astype(str) + " km/h"

    kepler_config = json.load(open("kepler_configs/dot_map.json"))
    map_1 = keplergl.KeplerGl(height=500, data={"Speed": gdf}, config=kepler_config)
    map_1.save_to_html(file_name="docs/plots/dot_map.html", config=kepler_config, read_only=True)

    return

def corridor_map():
    corridors = gpd.read_file("roads/corridors.geojson").set_crs("EPSG:4326").to_crs("EPSG:26910")

    #add names to each corridor: Mckenzie, Fort St West, Fort St East, Foul Bay, Henderson, Quadra
    corridors["corridor"] = ["Mckenzie", "Fort St West", "Fort St East", "Foul Bay", "Hillside", "Quadra","Douglas Core","Douglas North", "Pandora West", "Pandora East", "Shelbourne South", "Shelbourne North", "Johnson", "Oak Bay"]
    corridors['Average Speed'] = 0
    timeline = retrieve_timeline()
    
    selected_routes = {
        "Mckenzie": ["26"],
        "Fort St West": ["14", "15", "11"],
        "Fort St East": ["14", "15", "11"],
        "Foul Bay": ["7", "15"],
        "Hillside": ["4"],
        "Quadra": ["6"],
        "Douglas Core": ["95"],
        "Douglas North": ["95"],
        "Pandora West": ["2", "5", "27", "28"],
        "Pandora East": ["2", "5", "27", "28"],
        "Shelbourne South": ["27", "28"],
        "Shelbourne North": ["27", "28"],
        "Johnson": ["2", "5", "27", "28"],
        "Oak Bay": ["2", "5"]
    }

    #for map_name, y_var, title in [("system_speed_map", "Speed", "Average All-Day Speed"), ("system_speed_peak_map", "Speed", "Average Speed (8am-11am)"), ("system_peak_variability_map", "Speed Variability", "Speed Variability (8am-11am)")]:
    
 
    for corridor in corridors.corridor:
        filtered_timeline = timeline[timeline.Route.isin(selected_routes[corridor])].reset_index()
        buffer = corridors[corridors.corridor == corridor].buffer(20, cap_style=2)
        buffer = gpd.GeoDataFrame(buffer, geometry=buffer, crs="EPSG:26910")

        #filter timeline to only include points within buffer
        filtered_timeline = filtered_timeline[filtered_timeline.geometry.within(buffer.unary_union)]

        #calculate average speed and update corridor dataframd
        avg_speed = filtered_timeline.Speed.mean()
        avg_speed = round(avg_speed, 1)
        corridors.loc[corridors.corridor == corridor, "Average Speed"] = avg_speed

    corridors = corridors.to_crs("EPSG:4326")

    corridors['Speed Data'] = corridors['Average Speed'].round(1)
    corridors['colour'] = np.where(corridors['Speed Data'] > 50, 50, corridors['Speed Data'])
    corridors['Speed'] = corridors['Speed Data'].astype(str) + " km/h"

    kepler_config = json.load(open("kepler_configs/corridor_map.json"))
    map_1 = keplergl.KeplerGl(height=1000, data={"Speed": corridors}, config=kepler_config)
    map_1.save_to_html(file_name="docs/plots/corridor_map.html", config=kepler_config, read_only=True)
    
    return

def all_routes_bar_chart():
    timeline = retrieve_timeline()

    timeline['Hour'] = timeline.Datetime.dt.hour

    timeline = timeline[(timeline.Hour == 8) | (timeline.Hour == 9) | (timeline.Hour == 10)]

    timeline.Route = timeline.Route.astype(str)

    pivot = pd.pivot_table(timeline, values='Speed', index='Route', aggfunc='mean')

    #order by speed, highest to lowest
    pivot = pivot.sort_values(by='Speed', ascending=True).reset_index()

    #set timeline.Frequency to one of Local, FTN, RTN
    pivot['Frequency'] = "Local"
    for route in pivot.Route:
        if route in ['70', '95', '15']:
            pivot.loc[pivot.Route == route, "Frequency"] = "RTN"
        elif route in ['4', '6', '26', '14', '27', '28']:
            pivot.loc[pivot.Route == route, "Frequency"] = "FTN"
    
    color_discrete_map = {"Local": "#A8A8A8", "FTN": "#4A90E2", "RTN": "#F5A623"}

    fig = px.bar(pivot, y="Speed", x="Route", orientation="v", color="Frequency", color_discrete_map=color_discrete_map, labels={"Speed": "Average Speed (km/hr)", "route": "Route"},
    #order bars by speed, highest to lowest
    category_orders={"Route": pivot.Route})

    fig.update_layout(title_text="Average Speed by Route (8am-11am)", title_x=0.5)
    fig.write_html("docs/plots/all_routes_bar_chart.html")

    return

def runtimes_by_time():
    trips = summarize_trip_data()
    #only use data from the last 30 days
    trips = trips[trips.Date >= trips.Date.max() - pd.Timedelta(days=30)]
    #only pick trips that were on a weekday - use time_min (currently in epoch time) to get the day of the week. Will need to turn epoch to datetime
    trips = trips[trips.Time_min.apply(lambda x: pd.to_datetime(x, unit='s').weekday() < 5)]

    #convert time_min to datetime. Data is epoch time, datetime needs to be i  -n PST
    trips['Time-only'] = pd.to_datetime(trips['Time_min'], unit='s', utc=True)
    #convert to PST
    trips['Time-only'] = trips['Time-only'].dt.tz_convert('America/Los_Angeles').dt.strftime('%H:%M:%S')

    #create datetime object from Time-only. Give it a date of 1/1/1970. Use the time from Time-only
    trips['Time-only'] = pd.to_datetime('2000-01-01 ' + trips['Time-only'])
    
    #increment the date by one day for times before 3am
    trips.loc[trips['Time-only'].dt.hour < 3, 'Time-only'] += pd.Timedelta(days=1)

    #sort low to high
    trips = trips.sort_values(by='Time-only')

    #round runtime to 1 decimal place
    trips['runtime'] = trips['runtime'].round(1)

    for route in trips.Route.unique():
        fig = go.Figure()
        route_trips = trips[trips.Route == route]
        for i in range(0, len(route_trips.Header.unique())):
            header = trips[trips.Route == route].Header.unique()[i]
            colour = px.colors.qualitative.Plotly[i]

            df = route_trips[route_trips.Header == header]

            #calculate 5th and 95th percentile using a central moving average
            df['y_5th_perc'] = df.runtime.rolling(window=10, min_periods=1, center=True).apply(lambda x: np.percentile(x, 5), raw=True)
            df['y_95th_perc'] = df.runtime.rolling(window=10, min_periods=1, center=True).apply(lambda x: np.percentile(x, 95), raw=True)

            x = df['Time-only'].astype('int64') // 10**9
            
            lowess = sm.nonparametric.lowess(df.runtime, x, frac=.3)
            lowess_5th_perc = sm.nonparametric.lowess(df.y_5th_perc, x, frac=.3)
            lowess_95th_perc = sm.nonparametric.lowess(df.y_95th_perc, x, frac=.3)

            y = lowess[:, 1]
            y_5th_perc = lowess_5th_perc[:, 1]
            y_95th_perc = lowess_95th_perc[:, 1]

            x=lowess[:, 0],
            x = pd.to_datetime(lowess[:, 0], unit='s')

            #add 5th and 95th percentile lines
            fig.add_trace(go.Scatter
            (
                x=x,
                y=y_5th_perc,
                mode='lines',
                name=f'{header} 5th Percentile',
                marker=dict(color=colour),
                line=dict(color=colour, width=1),
                hoverinfo='skip',
                showlegend=False
            ))

            fig.add_trace(go.Scatter
            (
                x=x,
                y=y_95th_perc,
                mode='lines',
                name=f'{header} 95th Percentile',
                marker=dict(color=colour),
                line=dict(color=colour, width=1),
                hoverinfo='skip',
                fill='tonexty',
                fillcolor=f'rgba({int(colour[1:3], 16)}, {int(colour[3:5], 16)}, {int(colour[5:7], 16)}, 0.1)',
                showlegend=False
            ))

            fig.add_trace(go.Scatter(
                x=x,
                y=y,
                mode='lines',
                name=f'{header} LOWESS',
                marker=dict(color=colour),
                line=dict(color=colour, width=2),
                showlegend=False
                
            ))

            fig.add_trace(go.Scatter(
                x=df['Time-only'], 
                y=df.runtime, 
                mode='markers', 
                name=header, 
                marker=dict(color=colour, opacity=0.5), 
                customdata=df[['Route', 'label', 'Header']],
                hovertemplate="<b>Runtime: %{y} minutes</b><br>Direction: %{customdata[2]}<br>Departure: %{customdata[1]}<br>Route: %{customdata[0]}<extra></extra>"
            ))
            
        fig.update_layout(legend=dict(
                    yanchor="top",
                    y=0.99,
                    xanchor="right",
                    x=.99
                ))
        
        #add title, center it
        fig.update_layout(title='Route {} Runtimes by Time'.format(route),
                xaxis_title='Time',
                yaxis_title='Runtime (minutes)',
                title_x=0.5)
        
        fig.add_annotation(text="5th and 95th Percentiles Shown", xref="paper", yref="paper", x=0.5, y=0.05, showarrow=False)

        fig.write_html("docs/plots/runtime_by_time/route " + str(route) + ".html")

    return  

def runtimes_by_date():

    trips = summarize_trip_data()

    #turn trips Time_min into a datetime object
    trips['Time_min'] = pd.to_datetime(trips['Time_min'], unit='s', utc=True)
    #convert to PST
    trips['Time_min'] = trips['Time_min'].dt.tz_convert('America/Los_Angeles')

    #aggregate by date, Route. Get the average runtime, bot percentile, and top percentile. Use groupby, agg, and lambda functions
    runtimes_df = trips.groupby(['Date', 'Route']).agg({'runtime': ['median', lambda x: np.percentile(x, 5), lambda x: np.percentile(x, 95)]}).reset_index()

    #columns
    runtimes_df.columns = ['Date', 'Route', 'mean_runtime', 'bot_percentile', 'top_percentile']
    
    #create datetime object from date
    runtimes_df['Date'] = pd.to_datetime(runtimes_df['Date'])

    #sort low to high
    runtimes_df = runtimes_df.sort_values(by='Date')

    #round to 2 decimal places
    runtimes_df['mean_runtime'] = runtimes_df['mean_runtime'].round(2)
    runtimes_df['bot_percentile'] = runtimes_df['bot_percentile'].round(2)
    runtimes_df['top_percentile'] = runtimes_df['top_percentile'].round(2)

    trips['runtime'] = trips['runtime'].round(2)

    for route in runtimes_df.Route.unique():
        df = runtimes_df[runtimes_df.Route == route]
        fig = go.Figure()

        colour = px.colors.qualitative.Plotly[0]

        #scatter plot of the data
        fig.add_trace(go.Scatter(
                x=trips.Time_min, 
                y=trips.runtime, 
                mode='markers', 
                name=str(route), 
                marker=dict(color=colour, opacity=0.25), 
                customdata=trips[['Route', 'label', 'Header']],
                hovertemplate="<b>Runtime: %{y} minutes</b><br>Direction: %{customdata[2]}<br>Departure: %{customdata[1]}<br>Route: %{customdata[0]}<extra></extra>",
                showlegend=False
            ))

        fig.add_trace(go.Scatter(x=df.Date,
                     y=df.mean_runtime,
                     mode='lines',
                     name="Route " + str(df.Route.iloc[0]),
                     marker=dict(color='darkblue'),
                     hovertemplate="<b>Mean Runtime: %{y} minutes</b><br>Date: %{x}"))
     
        fig.update_layout(title='Route {} Runtime by Date'.format(df.Route.iloc[0]),
                        xaxis_title='Date',
                        yaxis_title='Mean Runtime (minutes)')
        
        #centre title
        fig.update_layout(title_x=0.5)

        fig.write_html("docs/plots/runtime_by_date/route " + str(route) + ".html")

    return

#run all functions
def run_all():
    system_map()
    corridor_map()
    all_routes_bar_chart()
    runtimes_by_time()
    dot_map()
    runtimes_by_date()
    return

#run_all()