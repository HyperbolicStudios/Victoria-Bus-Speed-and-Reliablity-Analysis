import requests

def download_static_gtfs():
    gtfs_url = "https://bct.tmix.se/Tmix.Cap.TdExport.WebApi/gtfs/?operatorIds=48" #Victoria, BC Transit static data

    #download data and save to static folder
    response = requests.get(gtfs_url)
    with open("static/gtfs.zip", "wb") as f:
        f.write(response.content)
    
    return

from gtfs_segments import get_gtfs_segments
segments_df = get_gtfs_segments("static/gtfs.zip")