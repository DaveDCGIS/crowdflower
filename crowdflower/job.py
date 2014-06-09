import csv
import json
import zipfile
from pprint import pformat
from cStringIO import StringIO
import grequests


def read_zip_csv(zf):
    for zipinfo in zf.filelist:
        zipinfo_fp = zf.open(zipinfo)
        reader = csv.DictReader(zipinfo_fp)
        for row in reader:
            yield row


class Job(object):
    '''
    Read / Write attributes
        auto_order
        auto_order_threshold
        auto_order_timeout
        cml
        cml_fields
        confidence_fields
        css
        custom_key
        excluded_countries
        gold_per_assignment
        included_countries
        instructions
        js
        judgments_per_unit
        language
        max_judgments_per_unit
        max_judgments_per_contributor
        min_unit_confidence
        options
        pages_per_assignment
        problem
        send_judgments_webhook
        state
        title
        units_per_assignment
        webhook_uri

    Read-only attributes
        completed
        completed_at
        created_at
        gold
        golds_count
        id
        judgments_count
        units_count
        updated_at

    Not sure about:
        payment_cents

    '''
    READ_WRITE_FIELDS = ['auto_order', 'auto_order_threshold', 'auto_order_timeout', 'cml', 'cml_fields', 'confidence_fields', 'css', 'custom_key', 'excluded_countries', 'gold_per_assignment', 'included_countries', 'instructions', 'js', 'judgments_per_unit', 'language', 'max_judgments_per_unit', 'max_judgments_per_contributor', 'min_unit_confidence', 'options', 'pages_per_assignment', 'problem', 'send_judgments_webhook', 'state', 'title', 'units_per_assignment', 'webhook_uri']

    def __init__(self, job_id, connection):
        self.id = job_id
        self._connection = connection
        # cacheable:
        self._properties = {}
        self._units = {}

    def __json__(self):
        return self.properties

    def __repr__(self):
        return pformat(self.properties)

    @property
    def properties(self):
        if len(self._properties) == 0:
            self._properties = self._connection.request('/jobs/%s' % self.id)
        return self._properties

    @property
    def units(self):
        if len(self._units) == 0:
            self._units = self._connection.request('/jobs/%s/units' % self.id)
        return self._units

    def clear_units(self, parallel=20):
        reqs = (self._connection.grequest('/jobs/%s/units/%s' % (self.id, unit_id), method='DELETE')
            for unit_id in self.units.keys())
        for response in grequests.imap(reqs, size=parallel):
            yield response

    def upload(self, units):
        headers = {'Content-Type': 'application/json'}
        data = '\n'.join(json.dumps(unit) for unit in units)
        res = self._connection.request('/jobs/%s/upload' % self.id, method='POST', headers=headers, data=data)

        # reset cached units
        self._units = {}

        return res

    def update(self, props):
        params = {'job[%s]' % key: value for key, value in props.items()}
        self._properties = {}
        return self._connection.request('/jobs/%s' % self.id, method='PUT', params=params)

    def delete(self):
        return self._connection.request('/jobs/%s' % self.id, method='DELETE')

    def download(self, full=True):
        '''The resulting CSV will have headers like:

            _unit_id
                Integer
                Unique ID per unit
            _created_at
                Date: m/d/yyyy hh:mm:ss
            _golden
                Enum: "true" | "false"
            _canary
                Always empty, ???
            _id
                Integer
                Unique ID per judgment
            _missed
                ???
            _started_at
                Date: m/d/yyyy hh:mm:ss
                Can use
            _tainted
                Always false, ???
            _channel
                Enum: "neodev" | "clixsense" | [etc.]
            _trust
                Always 1, ???
            _worker_id
                Integer
                Unique ID per worker
            _country
                3-letter ISO code
            _region
                String
                A number for all countries except UK, USA, Canada (others?)
            _city
                String
                City name
            _ip
                String
                IPv4 address

        And then the rest just copies over whatever fields were originally used, e.g.:

            id
            text
            sentiment
            sentiment_gold
        '''
        # pulls down the csv endpoint, unzips it, and returns a list of all the rows
        params = dict(full='true' if full else 'false')
        # use .csv, not headers=dict(Accept='text/csv'), which Crowdflower rejects
        req = self._connection.create_request('/jobs/%s.csv' % self.id, method='POST', params=params)
        res = self._connection.send_request(req)
        # because ZipFile insists on seeking, we can't simply pass over the res.raw stream
        fp = StringIO()
        fp.write(res.content)
        # fp.seek(0)
        zf = zipfile.ZipFile(fp)
        # yield each row?
        return list(read_zip_csv(zf))
