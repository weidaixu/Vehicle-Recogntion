import { Canvas, useFrame } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { DAYLIGHT_TOKENS } from '../visualTheme'

const DEPTH_STRENGTH = [0.008, 0.018, 0.036, 0.062]

export function normalizePointer(clientX:number, clientY:number, width:number, height:number) {
  return { x:clientX/Math.max(width,1)*2-1, y:1-clientY/Math.max(height,1)*2 }
}

export function getLayerShift(pointerX:number, pointerY:number, layer:number, active:boolean) {
  const strength = DEPTH_STRENGTH[layer] ?? DEPTH_STRENGTH.at(-1)!
  const boost = active ? 1.35 : 1
  return { x:pointerX * strength * boost, y:pointerY * strength * .58 * boost }
}

export function getSceneTransform(pointerX:number, pointerY:number, active:boolean) {
  const boost = active ? 1.3 : 1
  return {
    rotateX:pointerY * 2.4 * boost,
    rotateY:pointerX * 3.8 * boost,
    translateX:pointerX * 8 * boost,
    translateY:pointerY * -5 * boost,
  }
}

function createParticles(count:number, depth:number) {
  const values=new Float32Array(count*3);let seed=9173+depth*7919
  const random=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296}
  for(let i=0;i<count;i++){
    values[i*3]=(random()-.5)*18
    values[i*3+1]=(random()-.5)*9
    values[i*3+2]=depth+(random()-.5)*.8
  }
  return values
}

function LightField({active}:{active:boolean}) {
  const far=useRef<THREE.Points>(null),near=useRef<THREE.Points>(null)
  const farGeometry=useMemo(()=>{const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(createParticles(80,-1),3));return g},[])
  const nearGeometry=useMemo(()=>{const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(createParticles(34,1),3));return g},[])
  useFrame(({clock},delta)=>{
    if(far.current){far.current.rotation.z=clock.elapsedTime*.006;far.current.position.x=Math.sin(clock.elapsedTime*.12)*.06}
    if(near.current){near.current.rotation.z=-clock.elapsedTime*(active?.035:.012);near.current.position.y=Math.sin(clock.elapsedTime*.22)*.04;const m=near.current.material as THREE.PointsMaterial;m.opacity=THREE.MathUtils.damp(m.opacity,active?.48:.25,3,delta)}
  })
  return <>
    <points ref={far} geometry={farGeometry}><pointsMaterial color="#b9c7c9" size={.018} transparent opacity={.18} depthWrite={false}/></points>
    <points ref={near} geometry={nearGeometry}><pointsMaterial color="#ff6671" size={.034} transparent opacity={.25} blending={THREE.AdditiveBlending} depthWrite={false}/></points>
  </>
}

export default function DepthBackground({active}:{active:boolean}) {
  useEffect(()=>{
    const root=document.documentElement.style
    root.setProperty('--scene-exposure',String(DAYLIGHT_TOKENS.sceneExposure));root.setProperty('--scene-saturation',String(DAYLIGHT_TOKENS.sceneSaturation))
    root.setProperty('--daylight-glass',DAYLIGHT_TOKENS.glass);root.setProperty('--daylight-ink',DAYLIGHT_TOKENS.ink)
    let frame=0
    const publish=(point:{x:number,y:number})=>{
      cancelAnimationFrame(frame)
      frame=requestAnimationFrame(()=>{
        const t=getSceneTransform(point.x,point.y,active)
        root.setProperty('--scene-rx',`${t.rotateX}deg`);root.setProperty('--scene-ry',`${t.rotateY}deg`)
        root.setProperty('--scene-x',`${t.translateX}px`);root.setProperty('--scene-y',`${t.translateY}px`)
      })
    }
    const move=(event:PointerEvent)=>publish(normalizePointer(event.clientX,event.clientY,window.innerWidth,window.innerHeight))
    const leave=()=>publish({x:0,y:0})
    window.addEventListener('pointermove',move,{passive:true});document.documentElement.addEventListener('mouseleave',leave)
    return()=>{cancelAnimationFrame(frame);window.removeEventListener('pointermove',move);document.documentElement.removeEventListener('mouseleave',leave)}
  },[active])

  return <div className={`depth-canvas ${active?'is-active':''}`} aria-hidden="true">
    <Canvas orthographic camera={{position:[0,0,5],zoom:92}} dpr={[1,1.35]} gl={{alpha:true,antialias:false,powerPreference:'high-performance'}}><LightField active={active}/></Canvas>
    <div className="depth-horizon"/><div className="depth-stage"><i/><i/><i/></div><div className="depth-scan"/>
    <div className="depth-flare depth-flare-left"/><div className="depth-flare depth-flare-right"/>
    <div className="depth-vignette"><span/><span/><span/><span/></div>
  </div>
}
