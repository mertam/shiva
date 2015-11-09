import struct
import urllib
import urllib2
import httplib
import re
import xml.etree.ElementTree
import whois
import urlparse
import requests

from phishing import samedomain,extractdomain

class RankProvider(object):
    """Abstract class for obtaining the page rank (popularity)
    from a provider such as Google or Alexa.
    TAKEN FROM https://github.com/aablack/websearchapp/blob/master/search/rank_provider.py
    """
    def __init__(self, host, proxy=None, timeout=30):
        """Keyword arguments:
        host -- toolbar host address
        proxy -- address of proxy server. Default: None
        timeout -- how long to wait for a response from the server.
        Default: 30 (seconds)

        """
        self._opener = urllib2.build_opener()
        if proxy:
            self._opener.add_handler(urllib2.ProxyHandler({"http": proxy}))

        self._host = host
        self._timeout = timeout

    def get_rank(self, url):
        """Get the page rank for the specified URL

        Keyword arguments:
        url -- get page rank for url

        """
        raise NotImplementedError("You must override get_rank()")


class AlexaTrafficRank(RankProvider):
    """ Get the Alexa Traffic Rank for a URL

    """
    def __init__(self, host="xml.alexa.com", proxy=None, timeout=30):
        """Keyword arguments:
        host -- toolbar host address: Default: joolbarqueries.google.com
        proxy -- address of proxy server (if required). Default: None
        timeout -- how long to wait for a response from the server.
        Default: 30 (seconds)

        """
        super(AlexaTrafficRank, self).__init__(host, proxy, timeout)

    def get_rank(self, url):
        """Get the page rank for the specified URL

        Keyword arguments:
        url -- get page rank for url

        """
        try:
            query = "http://%s/data?%s" % (self._host, urllib.urlencode((
                ("cli", 10),
                ("dat", "nsa"),
                ("ver", "quirk-searchstatus"),
                ("uid", "1234"),
                ("userip", "192.168.0.1"),
                ("url", url))))
    
            response = self._opener.open(query, timeout=self._timeout)
            if response.getcode() == httplib.OK:
                data = response.read()
    
                element = xml.etree.ElementTree.fromstring(data)
                for e in element.iterfind("SD"):
                    popularity = e.find("POPULARITY")
                    if popularity is not None:
                        return int(popularity.get("TEXT"))
        except:
            return -1
        return -1


class GooglePageRank(RankProvider):
    """ Get the google page rank figure using the toolbar API.
    Credits to the author of the WWW::Google::PageRank CPAN package
    as I ported that code to Python.

    """
    def __init__(self, host="toolbarqueries.google.com", proxy=None, timeout=30):
        """Keyword arguments:
        host -- toolbar host address: Default: toolbarqueries.google.com
        proxy -- address of proxy server (if required). Default: None
        timeout -- how long to wait for a response from the server.
        Default: 30 (seconds)

        """
        super(GooglePageRank, self).__init__(host, proxy, timeout)
        self._opener.addheaders = [("User-agent", "Mozilla/4.0 (compatible; \
GoogleToolbar 2.0.111-big; Windows XP 5.1)")]

    def get_rank(self, url):
        # calculate the hash which is required as part of the get
        # request sent to the toolbarqueries url.
        try:
            ch = '6' + str(self._compute_ch_new("info:%s" % (url)))
    
            query = "http://%s/tbr?%s" % (self._host, urllib.urlencode((
                ("client", "navclient-auto"),
                ("ch", ch),
                ("ie", "UTF-8"),
                ("oe", "UTF-8"),
                ("features", "Rank"),
                ("q", "info:%s" % (url)))))
    
            response = self._opener.open(query, timeout=self._timeout)
            if response.getcode() == httplib.OK:
                data = response.read()
                match = re.match("Rank_\d+:\d+:(\d+)", data)
                if match:
                    rank = int(match.group(1))
                    return int(rank)
        except:
            return -1
        return -1

    @classmethod
    def _compute_ch_new(cls, url):
        ch = cls._compute_ch(url)
        ch = ((ch % 0x0d) & 7) | ((ch / 7) << 2);

        return cls._compute_ch(struct.pack("<20L", *(cls._wsub(ch, i * 9) for i in range(20))))

    @classmethod
    def _compute_ch(cls, url):
        url = struct.unpack("%dB" % (len(url)), url)
        a = 0x9e3779b9
        b = 0x9e3779b9
        c = 0xe6359a60
        k = 0

        length = len(url)

        while length >= 12:
            a = cls._wadd(a, url[k+0] | (url[k+1] << 8) | (url[k+2] << 16) | (url[k+3] << 24));
            b = cls._wadd(b, url[k+4] | (url[k+5] << 8) | (url[k+6] << 16) | (url[k+7] << 24));
            c = cls._wadd(c, url[k+8] | (url[k+9] << 8) | (url[k+10] << 16) | (url[k+11] << 24));

            a, b, c = cls._mix(a, b, c)

            k += 12
            length -= 12

        c = cls._wadd(c, len(url));

        if length > 10: c = cls._wadd(c, url[k+10] << 24)
        if length > 9: c = cls._wadd(c, url[k+9] << 16)
        if length > 8: c = cls._wadd(c, url[k+8] << 8)
        if length > 7: b = cls._wadd(b, url[k+7] << 24)
        if length > 6: b = cls._wadd(b, url[k+6] << 16)
        if length > 5: b = cls._wadd(b, url[k+5] << 8)
        if length > 4: b = cls._wadd(b, url[k+4])
        if length > 3: a = cls._wadd(a, url[k+3] << 24)
        if length > 2: a = cls._wadd(a, url[k+2] << 16)
        if length > 1: a = cls._wadd(a, url[k+1] << 8)
        if length > 0: a = cls._wadd(a, url[k])

        a, b, c = cls._mix(a, b, c);

        # integer is always positive
        return c

    @classmethod
    def _mix(cls, a, b, c):
        a = cls._wsub(a, b); a = cls._wsub(a, c); a ^= c >> 13;
        b = cls._wsub(b, c); b = cls._wsub(b, a); b ^= (a << 8) % 4294967296;
        c = cls._wsub(c, a); c = cls._wsub(c, b); c ^= b >>13;
        a = cls._wsub(a, b); a = cls._wsub(a, c); a ^= c >> 12;
        b = cls._wsub(b, c); b = cls._wsub(b, a); b ^= (a << 16) % 4294967296;
        c = cls._wsub(c, a); c = cls._wsub(c, b); c ^= b >> 5;
        a = cls._wsub(a, b); a = cls._wsub(a, c); a ^= c >> 3;
        b = cls._wsub(b, c); b = cls._wsub(b, a); b ^= (a << 10) % 4294967296;
        c = cls._wsub(c, a); c = cls._wsub(c, b); c ^= b >> 15;

        return a, b, c

    @staticmethod
    def _wadd(a, b):
        return (a + b) % 4294967296

    @staticmethod
    def _wsub(a, b):
        return (a - b) % 4294967296


class WhoisAge(RankProvider):
    
    def __init__(self, host="", proxy=None, timeout=30):
        super(WhoisAge, self).__init__(host, proxy, timeout)
    
    def get_rank(self, url):
        try:
            domain = whois.query(url)
            if domain.__dict__['creation_date']:
                return domain.__dict__['creation_date']
        except Exception:
            return None
        return None
    
class RedirectCount(RankProvider):
    """
    taken from http://www.zacwitte.com/resolving-http-redirects-in-python
    """
    
    def __init__(self, host="", proxy=None, timeout=30):
        super(RedirectCount, self).__init__(host, proxy, timeout)
    
    def get_rank(self, url):
        real_url = url
        if not re.match('(:i)^https?://', url):
            real_url = 'http://' + url
        return self.resolve_http_redirect(real_url)
    
    def resolve_http_redirect(self, url, depth=0):
       
        try:
            if depth > 10:
                return depth
            o = urlparse.urlparse(url,allow_fragments=True)
            conn = httplib.HTTPConnection(o.netloc)
            path = o.path
            if o.query:
                path +='?'+o.query
            conn.request("HEAD", path)
            res = conn.getresponse()
            headers = dict(res.getheaders())
            
            if headers.has_key('location') and headers['location'] != url:
                return self.resolve_http_redirect(headers['location'], depth+1)
            else:
                return depth
        except Exception:
            return -1

class LongUrl(RankProvider):
    
    def __init__(self, host="", proxy=None, timeout=30):
        super(LongUrl, self).__init__(host, proxy, timeout)
        
    def get_rank(self, url):
        try:

            req_url = 'http://api.longurl.org/v2/expand'
            params = {'format':'json', 'url':url}
            
            data = urllib.urlencode(params)
            
            r = requests.get(req_url + '?' + data)
            response = r.json()
            if response and 'long-url' in response:
                response['long-url']             

        except Exception:
            return ''
        return ''

        
    
class PhishTank(RankProvider):
    
    def __init__(self, host="", proxy=None, timeout=30):
        super(PhishTank, self).__init__(host, proxy, timeout)
        
    def get_rank(self, url):
        try:
            req_url = 'http://checkurl.phishtank.com/checkurl/'
            params = {'format':'json',
                          'url': url,
                          'app_key':'7040a8150761bfaaccb6d18a8c90677b3ebf3a788c7eb977543d99ddf308b02d' 
                           }
            data = urllib.urlencode(params)
            r = requests.post(req_url,data=data)
            response = r.json()
            if response and 'in_database' in response:
                return response['in_database']
        except Exception:
            return False
        return False
    
    
def get_domain_info(url):
    domain = re.sub('https?://', '', url)
    result = {}
    result['raw_link'] = url
    providers = (AlexaTrafficRank(),  WhoisAge(), RedirectCount(), GooglePageRank(), LongUrl())
    for p in providers:
        result[p.__class__.__name__] = p.get_rank(domain)
    return result




    

