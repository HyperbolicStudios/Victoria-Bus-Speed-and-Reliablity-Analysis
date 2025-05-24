from shapely.geometry import Point
import geopandas as gpd
from gtfs_functions import Feed

def generate_lines():
    feed = Feed("static/gtfs.zip")

    roads = gpd.read_file("roads/raw_download.geojson")
    roads = roads.to_crs("EPSG:26910")

    #get route map
    route_map = feed.segments.to_crs("EPSG:26910")

    #filter roads to ensure we're only analyzing roads near route_map
    roads['road_id'] = roads.index

    # Create GeoDataFrames for start and end points
    start_pts = roads.geometry.apply(lambda x: x.coords[0])
    mid_pts = roads.geometry.apply(lambda x: x.interpolate(0.5, normalized=True))
    end_pts = roads.geometry.apply(lambda x: x.coords[-1])
    start_gdf = gpd.GeoDataFrame({'road_id': roads['road_id'], 'geometry': start_pts.apply(lambda x: Point(x))}, crs=roads.crs)
    mid_gdf = gpd.GeoDataFrame({'road_id': roads['road_id'], 'geometry': mid_pts.apply(lambda x: Point(x))}, crs=roads.crs)
    end_gdf = gpd.GeoDataFrame({'road_id': roads['road_id'], 'geometry': end_pts.apply(lambda x: Point(x))}, crs=roads.crs)

    start_gdf.geometry = start_gdf.buffer(20)
    mid_gdf.geometry = mid_gdf.buffer(20)
    end_gdf.geometry = end_gdf.buffer(20)

    start_gdf = gpd.sjoin(start_gdf, route_map, how="inner", predicate="intersects")
    mid_gdf = gpd.sjoin(mid_gdf, route_map, how="inner", predicate="intersects")
    end_gdf = gpd.sjoin(end_gdf, route_map, how="inner", predicate="intersects")

    #get a list of buffer_ids that appear in both start and end gdf
    start_ids = start_gdf.road_id.unique()
    mid_ids = mid_gdf.road_id.unique()
    end_ids = end_gdf.road_id.unique()
    # Create a set of common buffer_ids
    common_ids = set(start_ids) & set(mid_ids) & set(end_ids)

    #now filter roads by common_ids
    roads = roads[roads['road_id'].isin(common_ids)]

    return roads