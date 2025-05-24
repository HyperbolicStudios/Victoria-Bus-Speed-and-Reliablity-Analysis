import os
import requests
import shutil
import pandas as pd
import geopandas as gpd
import time
import zipfile

def download_latest_static_gtfs():
    gtfs_url = "https://bct.tmix.se/Tmix.Cap.TdExport.WebApi/gtfs/?operatorIds=48" #Victoria, BC Transit static data

    #delete everything in static folder, but not the folder itself
    shutil.rmtree("static")
    os.makedirs("static", exist_ok=True)
    #download data and save to static folder
    response = requests.get(gtfs_url)
    with open("static/gtfs.zip", "wb") as f:
        f.write(response.content)
    
    #unzip the file
    import zipfile
    with zipfile.ZipFile("static/gtfs.zip", "r") as zip_ref:
        zip_ref.extractall("static")
    for file in os.listdir("static"):
        if file.endswith(".txt"):
            #rename to csv
            os.rename(os.path.join("static", file), os.path.join("static", file.replace(".txt", ".csv")))   
    return

def download_roads():
    # Base URL for the ArcGIS REST API
    base_url = "https://mapservices.crd.bc.ca/arcgis/rest/services/Roads/MapServer"
    
    layer_id = 14

    # Full URL for the query operation
    query_url = f"{base_url}/{layer_id}/query"

    # Query parameters
    params = {
        "where": "TOTAL_NUMBER_OF_LANES IN (1,2,3,4,5,6)",  # Filter for roads with 2 lanes
        "outFields": "*",  # Retrieve all fields
        "f": "geojson",  # Output format
        "resultRecordCount": 3000,  # Max records per request
    }

    # Initialize variables for pagination
    result_offset = 0
    all_features = []

    while True:
        # Update the resultOffset parameter for pagination
        params["resultOffset"] = result_offset

        # Send the query request
        response = requests.get(query_url, params=params)

        # Check if the request was successful
        if response.status_code != 200:
            print(f"Failed to fetch data. HTTP status code: {response.status_code}")
            print(response.text)
            break

        # Parse the GeoJSON response
        geojson_data = response.json()

        # Extract features
        features = geojson_data.get("features", [])
        all_features.extend(features)

        # Check if there are more records to fetch
        if len(features) < params["resultRecordCount"]:
            # If fewer records are returned, we’ve fetched everything
            break

        # Increment the offset for the next batch
        result_offset += params["resultRecordCount"]

    # Load all features into a GeoDataFrame
    if all_features:
        gdf = gpd.GeoDataFrame.from_features(all_features)
        
        gdf = gdf.set_crs(epsg=4326).to_crs(epsg=26910)

        #download to parcels/raw_download.geojson
        gdf.to_file("roads/raw_download.geojson", driver='GeoJSON')
        print("All data retrieved")

        return
    
def download_transitland_feeds():

    api_key = os.environ.get('TRANSITLAND_API_KEY')

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
