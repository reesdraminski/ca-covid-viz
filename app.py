from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import csv, requests
from geojson import Point, Feature, FeatureCollection, dump
import os

# initialize Flask application
app = Flask(__name__, static_url_path="")

# configure and initialize SQLAlchemy database connection
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

COUNTY_URL = "https://raw.githubusercontent.com/nytimes/covid-19-data/master/us-counties.csv"
PRISON_URL = "https://raw.githubusercontent.com/uclalawcovid19behindbars/historical-data/main/data/CA-historical-data.csv"

# constants for the CSV file
DATE_INDEX = 0
COUNTY_INDEX = 1
STATE_INDEX = 2
CASES_INDEX = 4
DEATHS_INDEX = 5

class Day(db.Model):
    """
    The Student model that is stored in the SQL database.
    """
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(80))
    county = db.Column(db.String(80))
    state = db.Column(db.String(80))
    cases = db.Column(db.Integer)
    deaths = db.Column(db.Integer)

FACILITY_ID = 0
PRSN_STATE = 2
PRSN_NAME = 3
PRSN_DATE = 4
PRSN_RES_CONF = 6
PRSN_STAFF_CONF = 7
PRSN_RES_DEATHS = 8
PRSN_STAFF_DEATHS = 9
PRSN_RES_REC = 10
PRSN_STAFF_REC = 11
PRSN_POP_FEB20 = 21
PRSN_RES_POP = 22
PRSN_COUNTY = 33
PRSN_LAT = 34
PRSN_LON = 35

class Prison(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    facilityID = db.Column(db.Integer)
    state = db.Column(db.String(80))
    name = db.Column(db.String(80))
    date = db.Column(db.String(80))
    residentsConfirmed = db.Column(db.Integer)
    staffConfirmed = db.Column(db.Integer)
    residentsDeaths = db.Column(db.Integer)
    staffDeaths= db.Column(db.Integer)
    residentsRecovered = db.Column(db.Integer)
    staffRecovered = db.Column(db.Integer)
    popFebTwenty = db.Column(db.Integer)
    residentsPopulation= db.Column(db.Integer)
    county = db.Column(db.String(80))
    latitude = db.Column(db.Integer)
    longitude = db.Column(db.Integer)

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/date", methods=["POST"])
def get_data_by_date():
    """
    Responds to POST requests with a JSON with date: "YYYY-MM-DD".
    """

    # error checking to make sure there is a date
    if "date" not in request.json:
        return "You need to supply a date in your request JSON body.", 400 

    # get existing student object by id from request data
    county_date = request.json["date"]
    county_results = Day.query.filter_by(date=county_date).all()

    # roll back date until there are entries in the DB
    while len(list(county_results)) == 0:
        # convert the date string to a datetime object
        date_obj = datetime.strptime(county_date, "%Y-%m-%d")

        # roll back one day and convert back to string
        date_obj -= timedelta(days=1)
        county_date = datetime.strftime(date_obj, "%Y-%m-%d")

        # check database to see if there are entries for this date
        county_results = Day.query.filter_by(date=county_date).all()

    # convert Day objects into dictionaries that are easily JSON-ified
    county_data = []
    for result in county_results:
        entry = {
            "date": result.date,
            "county": result.county,
            "state": result.state,
            "cases": result.cases,
            "deaths": result.deaths
        }

        county_data.append(entry)

    # get existing student object by id from request data
    prison_date = request.json["date"]
    prison_results = Prison.query.filter_by(date=prison_date).all()

    # roll back date until there are entries in the DB
    while len(list(prison_results)) == 0:
        # convert the date string to a datetime object
        date_obj = datetime.strptime(prison_date, "%Y-%m-%d")

        # roll back one day and convert back to string
        date_obj -= timedelta(days=1)
        prison_date = datetime.strftime(date_obj, "%Y-%m-%d")

        # check database to see if there are entries for this date
        prison_results = Prison.query.filter_by(date=prison_date).all()

    # convert Prison objects into dictionaries that are easily JSON-ified
    prison_data = []
    for result in prison_results:
        entry = {
            "id": result.id,
            "facilityID": result.facilityID,
            "state": result.state,
            "name": result.name,
            "date": result.date,
            "residentsConfirmed": result.residentsConfirmed,
            "staffConfirmed": result.staffConfirmed,
            "residentsDeaths": result.residentsDeaths,
            "staffDeaths": result.staffDeaths,
            "residentsRecovered": result.residentsRecovered,
            "staffRecovered": result.staffRecovered,
            "popFebTwenty": result.popFebTwenty,
            "residentsPopulation": result.residentsPopulation,
            "county": result.county,
            "latitude": result.latitude,
            "longitude": result.longitude,
        }

        prison_data.append(entry)

    # return a JSON with the data that was found
    return {
        "countyDataDate": county_date,
        "countyData": county_data,
        "prisonDataDate": prison_date,
        "prisonData": prison_data
    }

def create_pointers():
    with open("CA-historical-data.csv") as csvfile:
        # create a CSV reader for the file
        reader = csv.reader(csvfile)

        prison_data = list(filter(lambda x: x[PRSN_STATE] == "California", reader))

    features = []
    
    # create DB objects for each CA entry from the CSV file
    pairs = []

    for entry in prison_data:
        if [entry[PRSN_LAT], entry[PRSN_LON]] not in pairs and entry[PRSN_LAT] != "NA":
            point = Point((float(entry[PRSN_LON]), float(entry[PRSN_LAT])))

            features.append(Feature(geometry=point, properties={
                "kind": "prison",
                "name": entry[PRSN_NAME],
                "facilityID": entry[FACILITY_ID]
            }))

            pairs.append([entry[PRSN_LAT], entry[PRSN_LON]])
                
    feature_collection = FeatureCollection(features)

    with open('myfile.geojson', 'w') as f:
        dump(feature_collection, f)


def init_db():
    db.create_all()

    r = requests.get(COUNTY_URL)

    decoded_content = r.content.decode('utf-8')

    cr = csv.reader(decoded_content.splitlines(), delimiter=',')

    cali_data = list(cr)

    for entry in cali_data:
        # record county name, daily cases, and daily deaths
        data = {
            "date": entry[DATE_INDEX],
            "county": entry[COUNTY_INDEX],
            "state": entry[STATE_INDEX],
            "cases": entry[CASES_INDEX],
            "deaths": entry[DEATHS_INDEX]
        }

        # create a Day object and add to the database
        db.session.add(Day(**data))

        # save the new student in the database
        db.session.commit()

    r = requests.get(PRISON_URL)

    decoded_content = r.content.decode('utf-8')

    cr = csv.reader(decoded_content.splitlines(), delimiter=',')

    prison_data = list(filter(lambda x: x[PRSN_STATE] == "California", cr))

    # create DB objects for each CA entry from the CSV file
    for entry in prison_data:
        # record county name, daily cases, and daily deaths
        data = {

            "facilityID": entry[FACILITY_ID],
            "state": entry[PRSN_STATE],
            "name": entry[PRSN_NAME],
            "date": entry[PRSN_DATE],
            "residentsConfirmed": entry[PRSN_RES_CONF],
            "staffConfirmed": entry[PRSN_STAFF_CONF],
            "residentsDeaths": entry[PRSN_RES_DEATHS],
            "staffDeaths": entry[PRSN_STAFF_DEATHS],
            "residentsRecovered": entry[PRSN_RES_REC],
            "staffRecovered": entry[PRSN_STAFF_REC],
            "popFebTwenty": entry[PRSN_POP_FEB20], 
            "residentsPopulation": entry[PRSN_RES_POP], 
            "county": entry[PRSN_COUNTY],
            "latitude": entry[PRSN_LAT],
            "longitude": entry[PRSN_LON]
        }

        # create a Prison object and add to the database
        db.session.add(Prison(**data))

        # save the new student in the database
        db.session.commit()

def conv_states_to_file():

    basepath = './USA' # maybe just '.'

    print(os.listdir(basepath))

    for dir_name in os.listdir(basepath):

        dir_path = os.path.join(basepath, dir_name)

        print(dir_path)

        if not os.path.isdir(dir_path):
            continue

        with open('states.geo.json' , 'a') as outfile:


            for file_name in os.listdir(dir_path):
                if not file_name.endswith('.txt'):
                    continue

                file_path = os.path.join(dir_path, file_name)

                print(file_path)

                with open(file_path) as infile:

                    for line in infile:

                        outfile.write(line)

                outfile.write(',')