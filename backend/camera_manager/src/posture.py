"""Conservative pose evidence. Hidden joints are uncertainty, never proof of sitting."""
import math

def posture_evidence(keypoints, min_conf=.35):
    seated, standing = 0, 0
    for shoulder, hip, knee, ankle in ((5, 11, 13, 15), (6, 12, 14, 16)):
        if any(keypoints[i][2] < min_conf for i in (shoulder, hip, knee)):
            continue
        s, h, k, a = (keypoints[i] for i in (shoulder, hip, knee, ankle))
        torso = math.hypot(h[0]-s[0], h[1]-s[1])
        if torso < 8:
            continue
        dx, dy = abs(k[0]-h[0]), k[1]-h[1]
        # Bent/projected thigh with a visible hip and knee supports sitting.
        if -.15*torso <= dy < .65*torso and dx > .18*torso:
            seated += 1
        if a[2] >= min_conf:
            u=(h[0]-k[0], h[1]-k[1]); v=(a[0]-k[0], a[1]-k[1])
            norm=math.hypot(*u)*math.hypot(*v)
            angle=math.degrees(math.acos(max(-1,min(1,(u[0]*v[0]+u[1]*v[1])/norm)))) if norm else 0
            if angle > 155 and dy > .75*torso and a[1] > k[1]:
                standing += 1
    if standing and seated:
        return 'uncertain'
    return 'standing' if standing else 'seated' if seated else 'uncertain'

def iou(a,b):
    inter=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-inter
    return inter/union if union>0 else 0
