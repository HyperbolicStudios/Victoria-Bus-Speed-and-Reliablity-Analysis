import os
import requests
import shutil
import geopandas as gpd

def download_static_gtfs():
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

#download_static_gtfs()

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
    
download_roads()