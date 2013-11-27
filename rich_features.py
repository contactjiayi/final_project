import cv2
import numpy as np

class Point3D(object):
    def __init__(self, coords, origin):
        self.coords = coords
        self.origin = origin

def find_keypoints_descriptors(img):
    '''Detects keypoints and computes their descriptors.'''
    # initiate detector
    detector = cv2.SURF()

    # find the keypoints and descriptors
    kp, des = detector.detectAndCompute(img, None)

    return kp, des

def match_keypoints(kp1, des1, kp2, des2):
    '''Matches the descriptors in one image with those in the second image using
    the Fast Library for Approximate Nearest Neighbours (FLANN) matcher.'''
    MIN_MATCH_COUNT = 10

    # FLANN parameters
    FLANN_INDEX_KDTREE = 0
    index_params = dict(algorithm = FLANN_INDEX_KDTREE, trees = 5)
    search_params = dict(checks=50)   # or pass empty dictionary

    flann = cv2.FlannBasedMatcher(index_params,search_params)
    matches = flann.knnMatch(np.asarray(des1, np.float32), np.asarray(des2, np.float32), k=2)

    # store all the good matches as per Lowe's ratio test
    good_matches = []
    for m, n in matches:
        if m.distance < 0.7 * n.distance:
            good_matches.append(m)

    if len(good_matches) > MIN_MATCH_COUNT:
        src_pts = np.float32([ kp1[m.queryIdx].pt for m in good_matches ]).reshape(-1,1,2)
        dst_pts = np.float32([ kp2[m.trainIdx].pt for m in good_matches ]).reshape(-1,1,2)
        # filtered keypoints are lists containing the indices into the keypoints and descriptors
        filtered_kp1 = np.array([ m.queryIdx for m in good_matches ])
        filtered_kp2 = np.array([ m.trainIdx for m in good_matches ])

    else:
        print "Not enough matches were found - %d/%d" % (len(good_matches), MIN_MATCH_COUNT)

    # src_pts and dst_pts are Nx1x2 arrays that contain the x and y pixel coordinates
    return src_pts, dst_pts, filtered_kp1, filtered_kp2

def filter_keypoints(mask, filtered_kp1, filtered_kp2):
    '''Filter the keypoints using the mask of inliers generated by findFundamentalMat.'''
    # filtered_kp are lists containing the indices into the keypoints and descriptors
    filtered_kp1 = filtered_kp1[mask.ravel()==1]
    filtered_kp2 = filtered_kp2[mask.ravel()==1]

    return filtered_kp1, filtered_kp2

def attach_indices(i, pts_3D, filtered_kp1, filtered_kp2, pt_cloud_indexed=[]):
    '''Attach to each 3D point, indices into the original lists of keypoints and descriptors 
    of the 2D points that contributed to this 3D point in the cloud.'''

    def find_point(new_pt, pt_cloud_indexed):
        for old_pt in pt_cloud_indexed:
            try:
                if new_pt.origin[i] == old_pt.origin[i]:
                    return True, old_pt
            except KeyError:
                continue
        return False, None

    new_pts = []
    for num, pt in enumerate(pts_3D):
            new_pt = Point3D(pt, {i: filtered_kp1[num], i+1: filtered_kp2[num]})
            new_pts.append(new_pt)

    if pt_cloud_indexed == []:
        pt_cloud_indexed = new_pts
    else:
        for num, new_pt in enumerate(new_pts):
            found, old_pt = find_point(new_pt, pt_cloud_indexed)
            if found:
                old_pt.origin[i+1] = filtered_kp2[num]
            else:
                pt_cloud_indexed.append(new_pt)

    return pt_cloud_indexed

def scan_cloud(i, prev_kp, prev_des, prev_filter, filtered_kp, pt_cloud_indexed):
    '''Check for matches between the new frame and the current point cloud.'''
    # prev_filter contains the indices into the list of keypoints from the second image in the last iteration
    # filtered_kp contains the indices into the list of keypoints from the first image in the current iteration
    # the second image in the last iteration is the first image in the current iteration
    # therefore, check for matches by comparing the indices
    indices_2D  = []
    matched_pts_2D = []
    matched_pts_3D = []

    for new_idx in filtered_kp:
        for old_idx in prev_filter:
            if new_idx == old_idx:
                # found a match: a keypoint that contributed to both the last and current point clouds
                indices_2D.append(new_idx)

    for idx in indices_2D:
        # pt_cloud_indexed is a list of 3D points from the previous cloud with their keypoint indices
        for pt in pt_cloud_indexed:
            try:
                if pt.origin[i] == idx:
                    matched_pts_3D.append( pt.coords )
                    break
            except KeyError:
                continue
        continue

    for idx in indices_2D:
        matched_pts_2D.append( prev_kp[idx].pt )

    matched_pts_2D = np.array(matched_pts_2D, dtype='float32')
    matched_pts_3D = np.array(matched_pts_3D, dtype='float32')

    return matched_pts_2D, matched_pts_3D