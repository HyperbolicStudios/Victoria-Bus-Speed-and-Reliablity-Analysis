import geopandas as gpd
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from create_shapes import generate_lines
import plotly.express as px
import plotly.graph_objects as go

def retrieve_timeline():
    timeline = pd.read_csv("timeline.csv")

    #turn into geopandas dataframe based on x and y
    timeline = gpd.GeoDataFrame(timeline, geometry=gpd.points_from_xy(timeline.x, timeline.y))
    timeline = timeline.set_crs("EPSG:4326").to_crs("EPSG:26910")

    #turn 'Time' into Datetime column
    timeline['Datetime'] = pd.to_datetime(timeline['Time'], unit='s', utc=True)
    #convert to PST
    timeline['Datetime'] = timeline['Datetime'].dt.tz_convert('America/Los_Angeles')
    return(timeline)

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
    timeline = retrieve_timeline()

    #remove rows with a speed of 0
    timeline = timeline[timeline.Speed != 0]

    #ensure only weekdays are included
    timeline['day_of_week'] = timeline.Datetime.dt.dayofweek
    timeline = timeline[(timeline.day_of_week != 5) & (timeline.day_of_week != 6)]

    #Create a new date column, in the format YYYY-MM-DD
    timeline['Date'] = timeline.Datetime.dt.date
   
    #create a new custom_id column, which is the concatenation of the date and trip_id
    timeline['custom_id'] = timeline['Date'].astype(str) + timeline['Trip ID'].astype(str)
    #aggregate by custom_id, taking the difference between the first and last timestamp. This is the runtime
    runtimes_df = timeline.groupby(["custom_id"]).agg({"Time": ["min", "max"], 'Route': 'first'}).reset_index()

    runtimes_df['runtime'] = (runtimes_df['Time']['max'] - runtimes_df['Time']['min'])/60

    #get Time min, and convert it to datetime from epoch
    runtimes_df['Departure_Hour'] = pd.to_datetime(runtimes_df['Time']['min'], unit='s', utc=True).dt.tz_convert('America/Los_Angeles').dt.hour

    #turn two dimensional column names into one dimensional. Just the first element
    runtimes_df.columns = runtimes_df.columns.get_level_values(0)

    #aggregate by route, departure hour, and headsign. Get the average runtime, bot percentile, and top percentile. Use groupby, agg, and lambda functions
    runtimes_df = runtimes_df.groupby(['Route', 'Departure_Hour']).agg({'runtime': ['mean', lambda x: np.percentile(x, 5), lambda x: np.percentile(x, 95)]}).reset_index()

    
    runtimes_df.columns = ['Route', 'Departure_Hour', 'mean_runtime', 'bot_percentile', 'top_percentile']

    #replace NaN values of bot and top percentile with mean runtime
    runtimes_df['5th_percentile'] = runtimes_df['bot_percentile'].fillna(runtimes_df['mean_runtime'])
    runtimes_df['95th_percentile'] = runtimes_df['top_percentile'].fillna(runtimes_df['mean_runtime'])

    for route in runtimes_df.Route.unique():
        print(route)
        fig = go.Figure()

        df = runtimes_df[runtimes_df.Route == route]

        df = df.sort_values(by='Departure_Hour')

        #round to 2 decimal places
        df['mean_runtime'] = df['mean_runtime'].round(2)

        #plot the mean runtime, with bot and top percentiles        
        fig.add_trace(go.Scatter(x=df.Departure_Hour, y=df['top_percentile'], mode='lines', line=dict(width=0), showlegend=False, hovertemplate="<b>95th percentile:</b>%{y} minutes"))
        fig.add_trace(go.Scatter(x=df.Departure_Hour, y=df.mean_runtime, mode='lines', name="Route " + str(df.Route.iloc[0]), fill='tonexty', hovertemplate="<b>Mean:</b>%{y} minutes"))
        fig.add_trace(go.Scatter(x=df.Departure_Hour, y=df['bot_percentile'], mode='lines', line=dict(width=0), showlegend=False, fill='tonexty', hovertemplate="<b>5th percentile:</b>%{y} minutes"))

        fig.update_layout(title='Route {} Runtime by Departure Hour'.format(df.Route.iloc[0]),
                        xaxis_title='Departure Hour',
                        yaxis_title='Mean Runtime (minutes)')
        
        #centre title
        fig.update_layout(title_x=0.5)
        #add a subtitle
        fig.add_annotation(text="5th and 95th Percentiles Shown", xref="paper", yref="paper", x=0.5, y=0.05, showarrow=False)

        # Show the plot
        fig.write_html("docs/plots/runtime_by_time/route " + str(route) + ".html")
    
    return

def runtimes_by_date():
    timeline = retrieve_timeline()

    #remove rows with a speed of 0
    timeline = timeline[timeline.Speed != 0]

    #Create a new date column, in the format YYYY-MM-DD
    timeline['Date'] = timeline.Datetime.dt.date
   
    #create a new custom_id column, which is the concatenation of the date and trip_id
    timeline['custom_id'] = timeline['Date'].astype(str) + timeline['Trip ID'].astype(str)
    #aggregate by custom_id, taking the difference between the first and last timestamp. This is the runtime
    runtimes_df = timeline.groupby(["custom_id"]).agg({"Time": ["min", "max"], 'Date': 'first', 'Route': 'first'}).reset_index()

    runtimes_df['runtime'] = (runtimes_df['Time']['max'] - runtimes_df['Time']['min'])/60

    #turn two dimensional column names into one dimensional. Just the first element
    runtimes_df.columns = runtimes_df.columns.get_level_values(0)

    #aggregate by date, Route. Get the average runtime, bot percentile, and top percentile. Use groupby, agg, and lambda functions
    runtimes_df = runtimes_df.groupby(['Date', 'Route']).agg({'runtime': ['mean', lambda x: np.percentile(x, 5), lambda x: np.percentile(x, 95)]}).reset_index()

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
        fig.add_trace(go.Scatter(x=df.Date, y=df['top_percentile'], mode='lines', line=dict(width=0), showlegend=False, hovertemplate="<b>95th Percentile: %{y} minutes</b><br>Date: %{x}"))
        fig.add_trace(go.Scatter(x=df.Date, y=df.mean_runtime, mode='lines', name="Route " + str(df.Route.iloc[0]), fill='tonexty', hovertemplate="<b>Mean Runtime: %{y} minutes</b><br>Date: %{x}"))
        fig.add_trace(go.Scatter(x=df.Date, y=df['bot_percentile'], mode='lines', line=dict(width=0), showlegend=False, fill='tonexty', hovertemplate="<b>5th Percentile: %{y} minutes</b><br>Date: %{x}"))

        fig.update_layout(title='Route {} Runtime by Date'.format(df.Route.iloc[0]),
                        xaxis_title='Date',
                        yaxis_title='Mean Runtime (minutes)')
        
        #centre title
        fig.update_layout(title_x=0.5)
        #add a subtitle
        fig.add_annotation(text="5th and 95th Percentiles Shown", xref="paper", yref="paper", x=0.5, y=0.05, showarrow=False)

        fig.write_html("docs/plots/runtime_by_date/route " + str(route) + ".html")

    return

runtimes_by_time()