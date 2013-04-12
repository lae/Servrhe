# -*- coding: utf-8 -*-
import time, re

def timeToInt(time):
    p = time.split(":")
    c = p.pop().split(".")
    ms = int((c.pop()+"000")[:3]) if len(p) > 1 else 0
    s = int(c.pop())
    m = int(p.pop()) if p else 0
    h = int(p.pop()) if p else 0
    return ((h * 60 + m) * 60 + s) * 1000 + ms

def intToTime(i, short = False):
    ms = i % 1000
    i /= 1000
    s = i % 60
    i /= 60
    m = i % 60
    h = i / 60
    h = str(h) if short else ("00" + str(h))[-2:]
    m = ("00" + str(m))[-2:]
    s = ("00" + str(s))[-2:]
    ms = ("00" + str(ms/10))[-2:] if short else (("000" + str(ms))[-3:] + "000000000")[:9]
    return "%s:%s:%s.%s" % (h, m, s, ms)

class SubParser(object):
    info_output = ("Title","PlayResX","PlayResY","ScaledBorderAndShadow","ScriptType","WrapStyle")
    def __init__(self, filename = None):
        self.series = self.episode = None
        self.info = {}
        self.style_fields = []
        self.styles = {}
        self.event_fields = []
        self.events = []
        self.keywords = []
        if filename:
            self.load(filename)
    def load(self, filename):
        m = re.match(r"(.+?)(\d+)(-|_)", filename)
        if m:
            self.series = m.group(1)
            self.episode = m.group(2)
        with open(filename) as f:
            INFO, STYLE, EVENT = range(3)
            state = None
            for line in f:
                line = line.strip()
                if not line:
                    continue
                elif line == "﻿[Script Info]":
                    state = INFO
                elif line == "[V4+ Styles]":
                    state = STYLE
                elif line == "[Events]":
                    state = EVENT
                elif state == INFO:
                    if line[0] == ";":
                        continue
                    key, value = line.split(": ",1)
                    self.info[key] = value
                elif state == STYLE:
                    key, value = line.split(": ",1)
                    if key == "Format":
                        self.style_fields = [v.strip() for v in value.split(",")]
                    elif key == "Style":
                        s = dict(zip(self.style_fields, [v.strip() for v in value.split(",", len(self.style_fields)-1)]))
                        self.styles[s["Name"]] = s
                elif state == EVENT:
                    key, value = line.split(": ",1)
                    if key == "Format":
                        self.event_fields = [v.strip() for v in value.split(",")]
                    elif key == "Dialogue" or key == "Comment":
                        s = dict(zip(self.event_fields, [v.strip() for v in value.split(",", len(self.event_fields)-1)]))
                        s["time"] = timeToInt(s["Start"])
                        s["key"] = key
                        for k in ("MarginL","MarginR","MarginV"):
                            s[k] = str(int(s[k]))
                        if s["Text"][0] == "{" and s["Text"][-1] == "}" and "{" not in s["Text"][1:-1] and "}" not in s["Text"][1:-1]:
                            args = s["Text"][1:-1].split("|")
                            keyword = args.pop(0)
                            self.keywords.append({"line": len(self.events), "keyword": keyword, "args": args, "time": s["time"]})
                        self.events.append(s)
    def merge(self, other):
        if self.style_fields != other.style_fields:
            raise Exception("Style fields are not identical, can not merge.")
        if self.event_fields != other.event_fields:
            raise Exception("Event fields are not identical, can not merge.")
        self.merge_info(other)
        self.merge_styles(other)
        self.merge_events(other)
    def merge_info(self, other):
        self.info.update(other.info)
    def merge_styles(self, other):
        if self.style_fields != other.style_fields:
            raise Exception("Style fields are not identical, can not merge.")
        for k, v in other.styles.iteritems():
            if k in self.styles and v != self.styles[k]:
                print "'%s' style conflicts:" % k
                print "1: %s" % self.styles[k]
                print "2: %s" % v
                choice = 0
                while choice not in (1,2):
                    choice = int(raw_input("Select a style: "))
                if choice == 1:
                    continue
            self.styles[k] = v
    def merge_events(self, other):
        if self.event_fields != other.event_fields:
            raise Exception("Event fields are not identical, can not merge.")
        for keyword in other.keywords:
            keyword["line"] += len(self.events)
            self.keywords.append(keyword)
        self.events.extend(other.events)
    def sort(self):
        self.events.sort(self.time_sort)
    def time_sort(self, a, b):
        if a["time"] < b["time"]:
            return -1
        elif b["time"] < a["time"]:
            return 1
        else:
            return 0
    def __str__(self):
        self.sort()
        lines = []
        lines.append("[Script Info]")
        lines.append("Title: %s" % self.info["Title"])
        del self.info["Title"]
        info = self.info.items()
        info.sort()
        for k, v in info:
            if k in self.info_output:
                lines.append("%s: %s" % (k,v))
        lines.append("")
        lines.append("[V4+ Styles]")
        lines.append("Format: " + ", ".join(self.style_fields))
        styles = self.styles.items()
        styles.sort()
        for k, v in styles:
            l = []
            for k in self.style_fields:
                l.append(v[k])
            lines.append("Style: %s" % ",".join(l))
        lines.append("")
        lines.append("[Events]")
        lines.append("Format: " + ", ".join(self.event_fields))
        for v in self.events:
            l = []
            for k in self.event_fields:
                l.append(v[k])
            lines.append("%s: %s" % (v["key"], ",".join(l)))
        return "\n".join(lines)
    def create_style(self, style = {}, **kwargs):
        default = {
            "Name": "Default",
            "Fontname": "LTFinnegan Medium",
            "Fontsize": "50",
            "PrimaryColour": "&H00FFFFFF",
            "SecondaryColour": "&H000000FF",
            "OutlineColour": "&H00000000",
            "BackColour": "&H00000000",
            "Bold": "0",
            "Italic": "0",
            "Underline": "0",
            "StrikeOut": "0",
            "ScaleX": "100",
            "ScaleY": "100",
            "Spacing": "0",
            "Angle": "0",
            "BorderStyle": "1",
            "Outline": "2",
            "Shadow": "1",
            "Alignment": "2",
            "MarginL": "60",
            "MarginR": "60",
            "MarginV": "30",
            "Encoding": "1"
        }
        default.update(style)
        default.update(kwargs)
        self.styles[default["Name"]] = default
    def create_event(self, event = {}, **kwargs):
        default = {
            "Layer": "0",
            "Start": "0:00:00.00",
            "End": "1:00:00.00",
            "Style": "Default",
            "Name": "",
            "MarginL": "0",
            "MarginR": "0",
            "MarginV": "0",
            "Effect": "",
            "Text": "",
            "time": 0,
            "key": "Dialogue"
        }
        default.update(event)
        default.update(kwargs)
        self.events.append(default)

