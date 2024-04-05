from appicm.models import *
import csv
import os
import googlemaps


field_count = 5
CLLI_SAMPLE = 0
CLLI_LOCATION = 1
CLLI_CITY = 2
CLLI_STATE = 3
ACTUAL_CITY = 4

gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)


def run():
    with open(os.path.join("scripts", "clli.csv"), newline='') as csvfile:
        csv_reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        next(csv_reader)        # skip header

        for row in csv_reader:
            if len(row) >= field_count and row[ACTUAL_CITY] != "":
                obj, created = CLLI.objects.update_or_create(clli=row[CLLI_LOCATION],
                                                             defaults={"city": row[ACTUAL_CITY],
                                                                       "state": row[CLLI_STATE]})

                if not obj.geolocation:
                    geocode_result = gmaps.geocode(row[ACTUAL_CITY] + ", " + row[CLLI_STATE])
                    if len(geocode_result) > 0:
                        loc_raw = geocode_result[0].get("geometry", {}).get("location", None)
                        loc = str(loc_raw.get("lat")) + "," + str(loc_raw.get("lng"))
                    else:
                        # print(row[ACTUAL_CITY] + ", " + row[CLLI_STATE])
                        # print(geocode_result)
                        loc = ""

                    print("adding geolocation", obj)
                    obj.geolocation = loc
                    obj.save()
