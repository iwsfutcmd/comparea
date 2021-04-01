import copy
import json
import sys
from pyproj import Proj
from shapely.geometry import shape

'''
GeoJSON looks like:

    { type: "FeatureCollection",
      features: [
        type: "Feature",
        properties: { "a": "b", "c": 1.0 },
        geometry: { ... }
      ]}
'''

def check_feature(feature):
    '''Checks that a GeoJSON feature has the required attributes.

    Throws a descriptive error if anything is wrong.
    '''
    for prop in ['type', 'properties', 'id']:
        if prop not in feature:
            raise ValueError('Feature is missing "%s" field.' % prop)

    if feature['type'] != 'Feature':
        raise ValueError('Expected type=Feature, got type=%s' % feature['type'])

    for prop in ['name', 'population', 'population_year', 'area_km2', 'description']:
        if prop not in feature['properties']:
            raise ValueError('Feature is missing %s property' % prop)


def check_feature_collection(collection):
    if 'type' not in collection:
        raise ValueError('feature collection needs a "type" field.')

    if collection['type'] != 'FeatureCollection':
        raise ValueError('Expected type=FeatureCollection, got type=%s' % collection['type'])

    if 'features' not in collection or len(collection['features']) == 0:
        raise ValueError('FeatureCollection is missing features')

    for i, feature in enumerate(collection['features']):
        try:
            check_feature(feature)
        except ValueError as e:
            raise ValueError('(feature %d) %s' % (i, e))


pa = Proj("+proj=aea +lat_1=37.0 +lat_2=41.0")
def _lon_lats_to_shape(lon_lats, p=None):
    global pa
    if not p: p = pa
    lon, lat = list(zip(*lon_lats))
    x, y = p(lon, lat)
    cop = {"type": "Polygon", "coordinates": [list(zip(x, y))]}
    return shape(cop)


def get_area_of_polygon(lon_lats):
    '''lon_lats is an Nx2 list. Returns area in m^2.'''
    return _lon_lats_to_shape(lon_lats).area


def get_area_of_feature(feature):
    if feature['type'] == 'FeatureCollection':
        return sum([get_area_of_feature(feat) for feat in feature['features']])


    geom = feature['geometry']
    geoms = []
    if geom['type'] == 'GeometryCollection':
        geoms = geom['geometries']
    else:
        geoms = [geom]

    area = 0.0
    for geom in geoms:
        if geom['type'] == 'Polygon':
            if len(geom['coordinates']) > 0:
                area += get_area_of_polygon(geom['coordinates'][0])
        elif geom['type'] == 'MultiPolygon':
            area += sum([get_area_of_polygon(part[0]) for part in geom['coordinates']])
    return area


def get_convex_area_of_feature(feature):
    return convex_hull_of_feature(feature).area


def centroid_of_feature(feature):
    if feature['type'] == 'FeatureCollection':
        sums = [0, 0, 0]
        for feat in feature['features']:
            pt = centroid_of_feature(feat)
            A = get_area_of_feature(feat)
            sums[0] += pt[0] * A
            sums[1] += pt[1] * A
            sums[2] += A
        return sums[0] / sums[2], sums[1] / sums[2]

    geom = feature['geometry']
    geoms = []
    if geom['type'] == 'GeometryCollection':
        geoms = geom['geometries']
    else:
        geoms = [geom]

    sum_A = 0.0
    sum_x, sum_y = 0.0, 0.0
    for geom in geoms:
        if geom['type'] == 'Polygon':
            if len(geom['coordinates']) > 0:
                pt, A = _centroid_of_polygon(geom['coordinates'][0])
                sum_x += pt.x * A
                sum_y += pt.y * A
                sum_A += A
        elif geom['type'] == 'MultiPolygon':
            for part in geom['coordinates']:
                pt, A = _centroid_of_polygon(part[0])
                sum_x += pt.x * A
                sum_y += pt.y * A
                sum_A += A
    if sum_A != 0:
        return sum_x / sum_A, sum_y / sum_A
    else:
        return 0.0, 0.0


def _centroid_of_polygon(lon_lats):
    cop = {"type": "Polygon", "coordinates": [lon_lats]}
    s = shape(cop)
    return s.centroid, s.area


def bbox_of_feature(feature):
    '''Returns [minlat, minlon, maxlat, maxlon].'''
    if feature['type'] == 'FeatureCollection':
        bbox = None
        for feat in feature['features']:
            try:
                this_bbox = bbox_of_feature(feat)
                if not bbox:
                    bbox = this_bbox
                else:
                    bbox[0] = min(bbox[0], this_bbox[0])
                    bbox[1] = min(bbox[1], this_bbox[1])
                    bbox[2] = max(bbox[2], this_bbox[2])
                    bbox[3] = max(bbox[3], this_bbox[3])
            except ValueError:
                pass
        return bbox

    geom = feature['geometry']
    if geom['type'] == 'Polygon':
        return _bbox_of_polygon(geom['coordinates'][0])
    elif geom['type'] == 'MultiPolygon':
        bbox = None
        for part in geom['coordinates']:
            this_bbox = _bbox_of_polygon(part[0])
            if not bbox:
                bbox = this_bbox
            else:
                bbox[0] = min(bbox[0], this_bbox[0])
                bbox[1] = min(bbox[1], this_bbox[1])
                bbox[2] = max(bbox[2], this_bbox[2])
                bbox[3] = max(bbox[3], this_bbox[3])
        return bbox
    else:
        raise ValueError('Unsupported geometry: %s' % geom['type'])


def _bbox_of_polygon(lon_lats):
    lons = [x[0] for x in lon_lats]
    lats = [x[1] for x in lon_lats]
    return [min(lats), min(lons), max(lats), max(lons)]


def _make_multiploygon(geom, proj):
    if geom['type'] == 'Polygon':
        return _lon_lats_to_shape(geom['coordinates'][0], proj)
    elif geom['type'] == 'MultiPolygon':
        p = None
        for part in geom['coordinates']:
            shp = _lon_lats_to_shape(part[0], proj)
            if not p:
                p = shp
            else:
                p = p.union(shp)
        return p


def convex_hull_of_feature(feature):
    geom = feature['geometry']
    cx, cy = centroid_of_feature(feature)
    p = Proj(proj='sterea', lat_0=cy, lon_0=cx, k_0=0.9999079, x_0=0, y_0=0)
    return _make_multiploygon(geom, p).convex_hull


def solidity_of_feature(feature):
    return get_area_of_feature(feature) / get_convex_area_of_feature(feature)


def _is_coord_list_clockwise(coords):
    # see http://stackoverflow.com/a/1165943/388951
    return sum([(c1_c2[1][0]-c1_c2[0][0])*(c1_c2[1][1]+c1_c2[0][1]) for c1_c2 in zip(coords, coords[1:] + [coords[-1]])]) > 0


def make_polygons_clockwise(feature):
    assert 'type' in feature
    if feature['type'] == 'FeatureCollection':
        for feat in feature['features']:
            make_polygons_clockwise(feat)
    elif feature['type'] == 'Feature':
        geom = feature['geometry']['type']
        polys = []
        if geom == 'Polygon':
            polys = feature['geometry']['coordinates']
        elif geom == 'MultiPolygon':
            polys = [x[0] for x in feature['geometry']['coordinates']]
        for poly in polys:
            if not _is_coord_list_clockwise(poly):
                poly.reverse()


def subset_feature(in_feature, lng_range, lat_range):
    '''Return a feature containing only polygons centered in the box.'''
    feature = copy.deepcopy(in_feature)

    if feature['type'] == 'FeatureCollection':
        feature['features'] = [subset_feature(f, lng_range, lat_range) for f in feature['features']]
        return feature

    geom = feature['geometry']

    def is_in_bounds(polygon):
        pt, _ = _centroid_of_polygon(polygon)
        return (lng_range[0] < pt.x < lng_range[1] and
                lat_range[0] < pt.y < lat_range[1])

    geoms = []
    if geom['type'] == 'GeometryCollection':
        geoms = geom['geometries']
    else:
        geoms = [geom]

    for geom in geoms:
        if geom['type'] == 'Polygon':
            if not is_in_bounds(geom['coordinates'][0]):
                del geom['coordinates'][0]  # empty shape
        elif geom['type'] == 'MultiPolygon':
            indices_to_kill = []
            for idx, part in enumerate(geom['coordinates']):
                if not is_in_bounds(part[0]):
                    indices_to_kill.append(idx)
            for idx in reversed(indices_to_kill):
                del geom['coordinates'][idx]
    return feature


def add_feature_geometry(base_feature, new_feature):
    if base_feature['type'] == 'FeatureCollection':
        base_feature['features'].append(new_feature)
    elif base_feature['type'] == 'Feature':
        subfeature = copy.deepcopy(base_feature)
        base_feature['type'] = 'FeatureCollection'
        base_feature['features'] = [subfeature, new_feature]
        del base_feature['geometry']
    else:
        raise ValueError('Unknown feature type %s' % base_feature['type'])
