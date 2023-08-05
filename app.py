import geopandas as gpd
import plotly.express as px
import dash
from dash import dcc, html, Input, Output, State

gdf = gpd.read_file("analysis.geojson")

# Set up the Dash app
app = dash.Dash(__name__)
server = app.server

# Define the layout of the app
app.layout = html.Div([
    dcc.Graph(id='map', config={'scrollZoom': True}),
    dcc.Slider(
        id='hour-slider',
        min=gdf['Hour'].min(),
        max=gdf['Hour'].max(),
        value=gdf['Hour'].min(),
        marks={str(hour): str(hour) for hour in gdf['Hour'].unique()},
        step=None
    )
])

# Define the callback to update the chloropleth map and preserve the zoom level and center
@app.callback(
    Output('map', 'figure'),
    [Input('hour-slider', 'value')],
    [State('map', 'figure')]
)
def update_map(selected_hour, map_figure):
    filtered_data = gdf[gdf['Hour'] == selected_hour].reset_index(drop=True)

    # Replace this with your own chloropleth map generation logic using the GeoDataFrame (gdf)
    # Example: fig = px.choropleth_mapbox(gdf, ...)

    # For demonstration purposes, let's use a chloropleth mapbox plot instead
    fig = px.choropleth_mapbox(
        filtered_data,
        geojson=filtered_data.geometry,  # Use your actual GeoDataFrame here
        locations=filtered_data.index,  # Column in the GeoDataFrame with the location IDs
        color='Speed',  # Column in the GeoDataFrame with the data to be plotted
        mapbox_style='carto-positron',
        #colour on a red - yellow - green scale
        color_continuous_scale=["red", "yellow", "green"],
        #colour scale from 0 to 50
        range_color=(0, 50),
        zoom=11,
        center={'lat': 48.4566, 'lon': -123.3763},
        hover_data=['Speed', 'Hour'],
        #set height to 1000px
        height=600
    )

    #update figure to have no border around shapes
    fig.update_traces(marker_line_width=0, hovertemplate="<b>Speed: %{customdata[0]} km/h</b><br>Hour: %{customdata[1]}<br>"
    )

    # If the map_figure is not None, retain the existing zoom level and center
    if map_figure is not None:
        fig.update_layout(
            mapbox_zoom=map_figure['layout']['mapbox']['zoom'],
            mapbox_center=map_figure['layout']['mapbox']['center']
        )

    return fig

# Run the Dash app
if __name__ == '__main__':
    app.run_server(debug=True)