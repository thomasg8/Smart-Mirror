from tkinter import *
from random import randint
from time import strftime
from PIL import Image, ImageTk
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from cv2 import CascadeClassifier
import requests, pandas as pd, os, json, geocoder, cv2, numpy as np, datetime, pickle, os.path


class Weather():
    """Using Dark Sky API to get weather data (1000 requests per day)"""
    def __init__(self, size=42):
        """From your IP address, you location (lat, long) is determined and
        some non-changing details are initialized. Need to manually add apikey
        to credentials"""
        with open('credentials.json') as json_file:
            self.key = json.load(json_file)['darksky'] # https://darksky.net/dev
        with open('icons/mappings.json') as json_file:
            self.icons = json.load(json_file)
            self.size = size # size of icon image

        g = geocoder.ip('me')
        self.lat, self.long = g.latlng
        loc = g.geojson['features'][0]['properties']
        self.loc = loc['city'] + ", " +loc['state']

    def update(self):
        """Call the dark ky api and retrieve the relevant weather forecast
        api key manualled added to credentials file """
        r = requests.get('https://api.darksky.net/forecast/{}/{},{}'.format(self.key, str(self.lat), str(self.long)))
        self.data = json.loads(r.content); self.updated = int(strftime("%H"))
        self.temp = round(self.data['currently']['temperature'])
        self.summary = self.data['daily']['data'][0]['summary']
        self.icon = "icons/{}".format(self.icons[self.data['currently']['icon']])

class Calendar():
    """Retrieves calendar events from google calendar (must authorize) and download token.pickle
    https://developers.google.com/calendar/quickstart/python will get you started"""
    def __init__(self):
        SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
        creds = None
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
        self.service = build('calendar', 'v3', credentials=creds)

        # have to specify what calendar ids if not just base user calendar
        with open('calendar_ids.json') as json_file:
            self.c_ids = json.load(json_file)
        self.now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
        self.tomorrow = (datetime.datetime.utcnow() + datetime.timedelta(1)).isoformat() + 'Z'


    def update(self):
        self.events_raw = list()
        for v in self.c_ids.values():
            self.events_raw += self.service.events().list(calendarId=v, timeMin=self.now, maxResults=10, singleEvents=True,
                                        orderBy='startTime').execute().get('items', [])

        self.shortterm = list(); self.longterm = list(); self.all_es = list()
        if self.events_raw:
            for event in self.events_raw:
                try:
                    summary = event['summary'][:100]
                    end = datetime.datetime.strptime(event['end']['dateTime'][:16], "%Y-%m-%dT%H:%M")
                    start = datetime.datetime.strptime(event['start']['dateTime'][:16], "%Y-%m-%dT%H:%M")
                    duration_long = start.strftime("%m/%d %I:%M") +'-'+ end.strftime("%I:%M %p")
                    duration_short = start.strftime("%I:%M") +'-'+ end.strftime("%I:%M %p")
                    if start > datetime.datetime.now():
                        self.all_es.append([summary, duration_long, start])
                        if end < datetime.datetime.now() + datetime.timedelta(1):
                            self.shortterm.append([summary, duration_short, start])
                        else:
                            self.longterm.append([summary, duration_long, start])

                except:
                    pass
        self.todays_events = pd.DataFrame(self.shortterm, columns=['summary', 'duration', 'start'])
        self.all_events = pd.DataFrame(self.all_es, columns=['summary', 'duration', 'start'])

class News():
    """Retrieves latest news headlines"""
    def __init__(self):
        """api key manualled added to credentials file downloaded from google"""
        with open('credentials.json') as json_file:
            self.api_key = json.load(json_file)['newsapi']
        # get reuters top articles
        self.r  = requests.get("https://newsapi.org/v1/articles?source=reuters&sortBy=top&apiKey="+self.api_key).json()
        self.articles = self.r['articles']
        self.headlines = list(set([a['title'] for a in self.articles])) # had some duplicates, so just removed with set

class Hockey():
    def __init__(self):
        # MN Wild
        r = requests.get("http://statsapi.web.nhl.com/api/v1/teams/30?expand=team.schedule.next").json()
        ng = r['teams'][0]['nextGameSchedule']['dates'][0]['games'][0]
        self.next_game_date = r['gameDate']
        self.away = ng['teams']['away']['team']['name']
        self.home = ng['teams']['home']['team']['name']

class SmartMirror():
    """Displays and maintains the SmartMirror"""
    def __init__(self):
        """Initializes all of the values to be displayed and makes window"""
        # read in data
        self.weather = Weather(size=46); self.weather.update()
        self.calendar = Calendar(); self.calendar.update()
        self.news = News()

        self.window = Tk()
        self.window.configure(background='black')

        self.window.attributes("-fullscreen", True) # default is fullscreen
        self.window.bind("f", self.fullscreen) # press f key for fullscreen
        self.window.bind("<Escape>", self.end_fullscreen) # press escape for not full screen

        # init rows and columns
        [self.window.columnconfigure(i, weight=0) for i in [0,1,3,4]]
        self.window.columnconfigure(2, weight=1)
    def fullscreen(self, event=None):
        """Toggles to a fullscreen window"""
        self.window.attributes("-fullscreen", True)
        return "break"
    def end_fullscreen(self, event=None):
        """Toggles to a not full screen window"""
        self.window.attributes("-fullscreen", False)
        return "break"
    def initialize_items(self):
        """Initializes the items to be placed on window"""
        # edge columns allow for visual examination of wrap text
        self.edge_columns = [Label(text="1"*20, font = ('Times', 16, ''), bg="Black", fg="Black") for i in range(5)]
        # datetime - top middle
        self.date = Label(text=strftime("%A, %B %d, %Y"), font = ('Times', 24, ''), bg="Black", fg="white")
        self.time = Label(text = strftime('%I:%M:%S %p'), font = ('Times', 56, ''), bg="Black", fg="white")

        # weather - top left
        cv2img = cv2.imread(sm.weather.icon); cv2img = cv2.cvtColor(cv2img, cv2.COLOR_BGR2RGBA)
        cv2img = cv2.resize(cv2img, (sm.weather.size, sm.weather.size), interpolation = cv2.INTER_AREA)
        img = Image.fromarray(cv2img); photo = ImageTk.PhotoImage(image=img)
        self.icon = Label(image=photo, borderwidth=0, compound="center", highlightthickness = 0, padx=0 ,pady=0)
        self.icon.image = photo
        self.temp = Label(text=str(sm.weather.temp)+"\N{DEGREE SIGN}F", font = ('Times', 56, ''), bg="Black", fg="white")
        self.summary = Label(text=sm.weather.summary[:-1], font = ('Times', 24, ''), bg="Black", fg="white", wraplength = 32*25) # 24 pt font is 32 pixels
        self.loc = Label(text=sm.weather.loc, font = ('Times', 24, ''), bg="Black", fg="white", wraplength = 32*25)

        # calendar - middle left
        self.upcoming = Label(text= "Today's Events", font = ('Times', 24, ''), bg="Black", fg="white")
        self.specific = sm.calendar.todays_events
        if len(self.specific) != 0:
            self.cal_events_n = [Label(text=self.specific.sort_values('start').iloc[i,0],
                              font = ('Times', 18, ''), bg="Black", fg="white", wraplength = 150) for i in range(0,len(self.specific))]
            self.cal_times_n = [Label(text=self.specific.sort_values('start').iloc[i,1],
                              font = ('Times', 18, ''), bg="Black", fg="white", wraplength = 150) for i in range(0,len(self.specific))]

        #news - bottom
        self.newsfeed = Label(text= "Recent News", font = ('Times', 24, ''), bg="Black", fg="Black")
        self.n_news = 5
        self.news_events = [Label(text=sm.news.headlines[i],
                          font = ('Times', 14, ''), bg="Black", fg="white") for i in range(0,self.n_news)]

        # facial recognition - middle right
        self.capture = cv2.VideoCapture(0)
        self.video = Label()

    def place_items(self):
        """Assign items grid values"""
        for i in [0,1,3,4]: # set column length in a poor way
            self.edge_columns[i].grid(row=0, column=i)

        self.time.grid(row=1, column=2)
        self.date.grid(row=0, column=2)

        self.temp.grid(row=1, column=0, sticky = E)
        self.icon.grid(row=1, column=1, sticky = "NW")
        self.summary.grid(row=3, column=0, columnspan = 2)
        self.loc.grid(row=4, column=0, columnspan = 2)
        pad = max(0, 300-16*len(self.specific))

        if len(self.specific) != 0:
            self.upcoming.grid(row=5, column=0, sticky=W, pady = (pad, 0))
            for i in range(0,len(self.specific)):
                self.cal_events_n[i].grid(row=6+i, column=0, sticky = W)
                self.cal_times_n[i].grid(row=6+i, column=1, sticky = W)
            pad2 = 500
        pad2 = max(0, 20-16*len(self.specific))
        self.newsfeed.grid(row = 6 + len(self.specific),  columnspan = 5, pady = pad2)
        for i in range(0, self.n_news):
            self.news_events[i].grid(row = 7 + len(self.specific) + i, columnspan = 5)

        self.video.grid(column=3, row=6, columnspan=2, rowspan=max(len(self.specific), 1))

    def update_items(self):
        """Updates the video and time every 10 millesecond, and the data every 30 minutes
        The data update still requires more testing"""
        self.time.config(text = strftime('%I:%M:%S %p'))
        # every 30 minutes, updates data on screen
        now = datetime.datetime.now()

        if now.minute in [0, 30] and now.second == 0 and int(now.microsecond/1000)<10:
            self.weather.update()
            self.calendar.update()
            self.news = News()

            self.time.config(text = strftime('%I:%M:%S %p'))
            self.temp.config(text = str(sm.weather.temp)+"\N{DEGREE SIGN}F")
            photo = PhotoImage(file = sm.weather.icon)
            self.icon.config(image=photo); self.icon.image = photo
            self.summary.config(text=sm.weather.summary[:-1])

        ret, frame = self.capture.read()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # The haarcascade_frontalface_default.xml is a haar cascade designed by OpenCV to detect the frontal face
        # https://github.com/opencv/opencv/tree/master/data/haarcascades
        # I could create my own, but I need a lot of data and time that I do not have
        self.faceCascade = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")
        faces = self.faceCascade.detectMultiScale(gray, scaleFactor=1.3,
            minNeighbors=5, minSize=(30, 30))
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

        cv2img = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA), (240, 135), interpolation = cv2.INTER_AREA)
        img = Image.fromarray(cv2img)
        photo = ImageTk.PhotoImage(image=img)
        self.video.image = photo
        self.video.config(image=photo)
        self.video.after(10, self.update_items)

def main():
    sm.initialize_items(); sm.place_items()
    sm.update_items()
    sm.window.mainloop()
    sm.capture.release()

if __name__ == '__main__':
    sm = SmartMirror()
    main()
