"""Robust final 1080p composition, no distorted screenshots or oversized phone pads."""
from pathlib import Path
import math
import subprocess
from PIL import Image, ImageDraw, ImageFilter
import render as base


def mask(size, radius):
    im = Image.new("L",size)
    ImageDraw.Draw(im).rounded_rectangle((0,0,size[0]-1,size[1]-1),radius,fill=255)
    return im


class FinalRenderer(base.Renderer):
    def __init__(self):
        super().__init__()
        self.chassis, self.chassis_alpha = device_asset()
        self.base_cache = {i: self.static_scene(i,s) for i,s in enumerate(base.SCENES)}
        self.prepared = {}
        self.last_frame = None

    def thumbnail(self, name, t, scene, width, x, y, angle):
        if name not in self.prepared:
            self.prepared[name] = self.images[name].resize((448,970),Image.Resampling.LANCZOS)
        im = self.prepared[name].copy()
        # Pure photographic zoom: a centre crop retains the phone's proportions,
        # then the resized crop returns to the original phone-screen rectangle.
        zoom = 1.0 + 0.06 * math.sin(t*math.pi)
        w,h = round(448/zoom), round(970/zoom)
        im = im.crop(((448-w)//2,(970-h)//2,(448+w)//2,(970+h)//2)).resize((448,970),Image.Resampling.LANCZOS)
        phone = Image.new("RGBA",(486,1022))
        phone.alpha_composite(self.chassis,(0,0))
        phone.paste(im,(19,26),mask((448,970),25))
        draw=ImageDraw.Draw(phone)
        draw.rounded_rectangle((186,12,297,21),5,fill=(2,30,19))
        draw.ellipse((308,11,319,22),fill=(2,30,19))
        # A thin real-phone side, bounded by the entire phone alpha.
        device=Image.new("RGBA",(496,1030))
        a=phone.getchannel("A")
        edge=Image.new("RGBA",phone.size,(22,66,44,255))
        for dx,dy in [(2,8),(6,10)]:
            device.paste(edge,(dx,dy),a)
        device.alpha_composite(phone,(0,0))
        device=device.rotate(angle,Image.Resampling.BICUBIC,expand=True)
        ratio=width/device.width
        device=device.resize((width,round(device.height*ratio)),Image.Resampling.LANCZOS)
        out=Image.new("RGBA",(base.W,base.H))
        out.alpha_composite(device,(round(x-device.width/2),round(y-device.height/2)))
        return out

    def phone(self, name, t, scene, width=500,x=1388,y=526,yaw=0.0,pitch=0.0,roll=0.0,detail=1.0):
        # A sinusoidal roll travels into a mild side angle, then rights the phone.
        # This is rotation of the full photographic phone, not an opaque geometric mask.
        base_angle = yaw*95
        p=base.ease(t)
        angle=base_angle*(1.1-0.65*p)+math.sin(t*math.pi*2)*1.7
        scale=width*(0.96+0.06*p)
        position_x=x+(1-base.enter(t*1.2))*75*(1 if base.SCENES[3] is scene else -1)
        return self.thumbnail(name,t,scene,round(scale),position_x,y,angle)


def device_asset():
    im=Image.new("RGBA",(486,1022))
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((0,0,485,1021),47,fill=(35,91,58),outline=(113,155,125),width=3)
    d.rounded_rectangle((5,5,480,1016),42,fill=(6,48,31),outline=(67,117,76),width=3)
    return im,im.getchannel("A")


def final_main():
    r=FinalRenderer()
    r.frame(6,5.2).save(base.OUT/"review"/"final-clean-preview.png")
    for i,s in enumerate(base.SCENES):
        r.render_scene(i,output=base.BUILD/f"{i:02d}.mp4")
    cat=base.BUILD/"concat.txt"
    cat.write_text("\n".join(f"file '{(base.BUILD/f'{i:02d}.mp4').as_posix()}'" for i in range(len(base.SCENES))),encoding="utf-8")
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(cat),
                    "-i",str(base.OUT/"Svinkki-soundtrack.m4a"),"-map","0:v","-map","1:a",
                    "-c:v","copy","-c:a","copy","-movflags","+faststart","-t",str(base.TOTAL),
                    str(base.OUT/"Svinkki-demo-1080p.mp4")],check=True)
    r.frame(0,.6).save(base.OUT/"Svinkki-demo-poster.png")


if __name__=="__main__":
    final_main()
