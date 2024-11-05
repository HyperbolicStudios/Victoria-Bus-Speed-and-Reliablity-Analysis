import geopandas as gpd
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from create_shapes import generate_lines
import plotly.express as px
import plotly.graph_objects as go
import statsmodels.api as sm

#Retrieve the entire timeline (as points). Used for the system and corridor maps
def retrieve_timeline():
    timeline = pd.read_csv("timeline.csv")

    #turn into geopandas dataframe based on x and y
    timeline = gpd.GeoDataFrame(timeline, geometry=gpd.points_from_xy(timeline.x, timeline.y))
    timeline = timeline.set_crs("EPSG:4326").to_crs("EPSG:26910")

    #turn 'Time' into Datetime column
    timeline['Datetime'] = pd.to_datetime(timeline['Time'], unit='s', utc=True)
    #convert to PST
    timeline['Datetime'] = timeline['Datetime'].dt.tz_convert('America/Los_Angeles')

    #temporary fix for missing speed data
    timeline['Header'] = "Route " + timeline['Route'].astype(str)
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

    return(runtimes_df)

def system_map():
    route_segments = generate_lines()
    timeline = retrieve_timeline()
 
    #create a buffer around each line in lines, and create a new geodataframe with the buffers
    buffers = gpd.GeoDataFrame(geometry=route_segments.buffer(20, cap_style=2), crs="EPSG:26910")

    timeline['Hour'] = timeline.Datetime.dt.hour
    
    buffers = buffers.reset_index()
    buffers['buffer_id'] = buffers.index

    #spatial merge. Find all the points that are within buffers, and retain buffer geometry.
    timeline = gpd.sjoin(buffers, timeline, how="left", predicate="intersects")
  
    timeline = timeline[["Hour", "Speed", "buffer_id", "geometry"]]

    #aggregate by buffer_id. Aggregate Speed to average and geometry to first
    timeline = timeline.groupby(["buffer_id"]).agg({"Speed": "mean", "geometry": "first"}).reset_index()

    timeline = gpd.GeoDataFrame(timeline, geometry="geometry", crs="EPSG:26910")

    timeline = timeline.to_crs("WGS-84")

    timeline.Speed = timeline.Speed.round(0)

    fig = px.choropleth_mapbox(timeline, geojson=timeline.geometry, locations=timeline.index, color="Speed",
                            mapbox_style="carto-positron",
                            opacity=0.7,
                            labels={'Speed':'Average Speed (km/hr)'},
                            color_continuous_scale=["red", "yellow", "green"],
                            #colour scale from 0 to 50
                            range_color=(10, 50),
                            zoom=11,
                            center={'lat': 48.4566, 'lon': -123.3763},
                            hover_data=['Speed']
                            )
    
    fig.update_traces(marker_line_width=0, hovertemplate="<b>Average Speed: %{customdata[0]} km/h<br>")
    #add title, center it
    fig.update_layout(title_text="Average All-Day Speed (System-Wide)", title_x=0.5)
   
    fig.write_html("docs/plots/system_map.html")

    return

def corridor_map():
    corridors = gpd.read_file("corridors.geojson")

    #add names to each corridor: Mckenzie, Fort St West, Fort St East, Foul Bay, Henderson, Quadra
    corridors["corridor"] = ["Mckenzie", "Fort St West", "Fort St East", "Foul Bay", "Hillside", "Quadra","Douglas Core","Douglas North"]
    corridors['Average Speed'] = 0
    timeline = retrieve_timeline()
    
    selected_routes = {
        "Mckenzie": [26],
        "Fort St West": [14, 15, 11],
        "Fort St East": [14, 15, 11],
        "Foul Bay": [7, 15],
        "Hillside": [4],
        "Quadra": [6],
        "Douglas Core": [95],
        "Douglas North": [95]
    }
 
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

    corridors.geometry = corridors.buffer(20).to_crs("EPSG:4326")

    #map with plotly
    fig = px.choropleth_mapbox(corridors, geojson=corridors.geometry, locations=corridors.index, color="Average Speed",
                            mapbox_style="carto-positron",
                            opacity=0.7,
                            labels={'Average Speed':'Average Speed (km/hr)'},
                            color_continuous_scale=["red", "yellow", "green"],
                            #colour scale from 0 to 50
                            range_color=(0, 50),
                            zoom=11,
                            center={'lat': 48.4566, 'lon': -123.3763},
                            hover_data=['corridor', 'Average Speed']
                            )
    
    fig.update_traces(marker_line_width=0, hovertemplate="<b>%{customdata[0]}</b><br>Average Speed: %{customdata[1]} km/h<br>")
    #add title, center it
    fig.update_layout(title_text="Average Speed by Corridor", title_x=0.5)
   
    fig.write_html("docs/plots/corridor_map.html")
    return

def all_routes_bar_chart():
    timeline = retrieve_timeline()

    timeline['Hour'] = timeline.Datetime.dt.hour

    timeline = timeline[(timeline.Hour == 8) | (timeline.Hour == 9) | (timeline.Hour == 10)]

    timeline = timeline.groupby(["Route"]).agg({"Speed": "mean"}).reset_index()

    timeline = timeline.sort_values(by="Speed", ascending=True)
    
    timeline['Route'] = timeline.Route.astype(str)


    #set timeline.Frequency to one of Local, FTN, RTN
    timeline['Frequency'] = "Local"
    for route in timeline.Route:
        if route in ['70', '95', '15']:
            timeline.loc[timeline.Route == route, "Frequency"] = "RTN"
        elif route in ['4', '6', '26', '14', '27', '28']:
            timeline.loc[timeline.Route == route, "Frequency"] = "FTN"
    
    color_discrete_map = {"Local": "grey", "FTN": "blue", "RTN": "orange"}

    fig = px.bar(timeline, y="Speed", x="Route", orientation="v", color="Frequency", color_discrete_map=color_discrete_map, labels={"Speed": "Average Speed (km/hr)", "route": "Route"},
    #order bars by speed, highest to lowest
    category_orders={"Route": timeline.Route})

    fig.update_layout(title_text="Average Speed by Route", title_x=0.5)
    fig.write_html("docs/plots/all_routes_bar_chart.html")
           
def runtimes_by_time():
    trips = summarize_trip_data()
    #only pick trips that were on a weekday - use time_min (currently in epoch time) to get the day of the week. Will need to turn epoch to datetime
    trips = trips[trips.Time_min.apply(lambda x: pd.to_datetime(x, unit='s').weekday() < 5)]

    #convert time_min to datetime. Data is epoch time, datetime needs to be in PST
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

        for i in range(0, len(trips[trips.Route == route].Header.unique())):
            header = trips[trips.Route == route].Header.unique()[i]
            colour = px.colors.qualitative.Plotly[i]

            df = trips[(trips.Route == route) & (trips.Header == header)]

            #calculate 5th and 95th percentile using a central moving average
            y_5th_perc = df.runtime.rolling(window=15, center=True).apply(lambda x: np.percentile(x, 5), raw=True)
            y_95th_perc = df.runtime.rolling(window=15, center=True).apply(lambda x: np.percentile(x, 95), raw=True)

            x = df['Time-only'].astype('int64') // 10**9
            
            lowess = sm.nonparametric.lowess(df.runtime, x, frac=.3)
            lowess_5th_perc = sm.nonparametric.lowess(y_5th_perc, x, frac=.3)
            lowess_95th_perc = sm.nonparametric.lowess(y_95th_perc, x, frac=.3)

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
#system_map()
#corridor_map()
#all_routes_bar_chart()
runtimes_by_time()
#runtimes_by_date()
