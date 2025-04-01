# -*- coding: utf-8 -*-

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.

"""Extractors for https://www.wikifeet.com/"""

from .common import GalleryExtractor
from .. import text, util


class WikifeetGalleryExtractor(GalleryExtractor):
    """Extractor for image galleries from wikifeet.com"""
    category = "wikifeet"
    directory_fmt = ("{category}", "{celebrity}")
    filename_fmt = "{category}_{celeb}_{pid}.{extension}"
    archive_fmt = "{type}_{celeb}_{pid}"
    pattern = (r"(?:https?://)(?:(?:www\.)?wikifeetx?|"
               r"men\.wikifeet)\.com/([^/?#]+)")
    example = "https://www.wikifeet.com/CELEB"

    def __init__(self, match):
        self.root = text.root_from_url(match.group(0))
        if "wikifeetx.com" in self.root:
            self.category = "wikifeetx"
        self.type = "men" if "://men." in self.root else "women"
        self.celeb = match.group(1)
        GalleryExtractor.__init__(self, match, self.root + "/" + self.celeb)

    def metadata(self, page):
        extr = text.extract_from(page)
        return {
            "celeb"     : self.celeb,
            "type"      : self.type,
            "rating"    : text.parse_float(extr('"ratingValue": "', '"')),
            "celebrity" : text.unescape(extr("times'>", "</h1>")),
            "shoesize"  : text.remove_html(extr("Shoe Size:", "edit")),
            "birthplace": text.remove_html(extr("Birthplace:", "edit")),
            "birthday"  : text.parse_datetime(text.remove_html(
                extr("Birth Date:", "edit")), "%Y-%m-%d"),
        }

    def images(self, page):
        tagmap = {
            "C": "Close-up",
            "T": "Toenails",
            "N": "Nylons",
            "A": "Arches",
            "S": "Soles",
            "B": "Barefoot",
        }

        # Try to extract JSON data using multiple possible patterns
        json_data = None
        
        # Pattern 1: ['gdata'] = [...];
        json_str = text.extr(page, "['gdata'] = ", ";")
        if json_str:
            try:
                json_data = util.json_loads(json_str)
            except ValueError:
                json_data = None
        
        # Pattern 2: "gallery":[...]
        if not json_data:
            json_str = text.extr(page, '"gallery":', ']') + ']'
            if json_str and json_str != ']':
                try:
                    json_data = util.json_loads(json_str)
                except ValueError:
                    json_data = None
        
        # Fallback: Try to find any JSON array that looks like image data
        if not json_data:
            # This is a more general approach that might catch other formats
            json_str = text.extr(page, '[{"pid":"', '}]') + '}]'
            if json_str and json_str != '}]':
                try:
                    json_data = util.json_loads('[' + json_str)
                except ValueError:
                    json_data = None
        
        if not json_data:
            return []

        for data in json_data:
            # Use numeric URL format: https://pics.wikifeet.com/8514553.jpg
            image_url = "https://pics.wikifeet.com/{}.jpg".format(data["pid"])
            
            yield (image_url, {
                "pid": data["pid"],
                "width": data.get("pw", 0),  # Using .get() for safety
                "height": data.get("ph", 0),
                "tags": [tagmap[tag] for tag in data.get("tags", []) if tag in tagmap],
            })
