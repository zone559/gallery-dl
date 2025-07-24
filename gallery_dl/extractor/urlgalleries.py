# -*- coding: utf-8 -*-

from .common import GalleryExtractor, Message
from .. import text, exception
import re

class UrlgalleriesGalleryExtractor(GalleryExtractor):
    """Extractor for https://urlgalleries.net/ with updated Imagevenue support"""
    category = "urlgalleries"
    root = "https://urlgalleries.net"
    request_interval = (0.5, 1.5)
    pattern = (r"(?:https?://)()(?:(\w+)\.)?urlgalleries\.net"
               r"/(?:b/([^/?#]+)/)?(?:[\w-]+-)?(\d+)")
    example = "https://urlgalleries.net/b/BLOG/gallery-12345/TITLE"

    def _convert_imagevenue_url(self, url):
        """Convert Imagevenue thumbnail URL to direct image URL"""
        if not url:
            return None
            
        # Handle new Imagevenue CDN format (from the HTML snippet)
        if "cdno-data.imagevenue.com" in url:
            return url
            
        # Handle old Imagevenue thumbnail formats
        if "imagevenue.com" in url:
            patterns = [
                r'/(?:loc\d+/)?th?_(\d+_.*\.(?:jpg|png|gif|webp))',
                r'/(?:loc\d+/)?img_(\d+_.*\.(?:jpg|png|gif|webp))',
                r'/(\d+_.*\.(?:jpg|png|gif|webp))'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    server = url.split('/')[2].split('.')[0]
                    return f"https://{server}.imagevenue.com/img.php?image={match.group(1)}"
        
        return url.partition("?")[0]  # Return original URL without parameters

    def items(self):
        _, blog_alt, blog, self.gallery_id = self.groups
        if not blog:
            blog = blog_alt
        url = f"{self.root}/b/{blog}/porn-gallery-{self.gallery_id}/?a=10000"

        with self.request(url, allow_redirects=False, fatal=...) as response:
            if 300 <= response.status_code < 500:
                if response.headers.get("location", "").endswith(
                        "/not_found_adult.php"):
                    raise exception.NotFoundError("gallery")
                raise exception.HttpError(None, response)
            page = response.text

        imgs = self.images(page)
        data = self.metadata(page)
        data["count"] = len(imgs)

        yield Message.Directory, data
        for data["num"], img_url in enumerate(imgs, 1):
            if not img_url:
                continue
                
            try:
                # Handle both old and new Imagevenue formats
                direct_url = self._convert_imagevenue_url(img_url)
                if direct_url:
                    yield Message.Queue, direct_url, data
            except Exception as e:
                self.log.warning("Failed to process image URL %s: %s", img_url, str(e))

    def metadata(self, page):
        extr = text.extract_from(page)
        return {
            "gallery_id": self.gallery_id,
            "_site": extr(' title="', '"'),
            "blog": text.unescape(extr(' title="', '"')),
            "_rprt": extr(' title="', '"'),
            "title": text.unescape(extr(' title="', '"').strip()),
            "date": text.parse_datetime(
                extr(" images in gallery | ", "<"), "%B %d, %Y"),
        }

    def images(self, page):
        """Extract all image URLs from the page"""
        imgs = []
        
        # First try new CDN format (from the HTML snippet)
        cdn_urls = list(text.extract_iter(page, 'src="https://cdno-data.imagevenue.com/', '"'))
        for url in cdn_urls:
            imgs.append(f"https://cdno-data.imagevenue.com/{url.split('"')[0]}")
        
        # Fall back to old thumbnail format if no CDN URLs found
        if not imgs:
            wtf_section = text.extr(page, 'id="wtf"', "</div>")
            if wtf_section:
                imgs = list(text.extract_iter(wtf_section, " src='", "'"))
        
        # Filter valid URLs only
        return [url for url in imgs if url and url.startswith(('http://', 'https://'))]
