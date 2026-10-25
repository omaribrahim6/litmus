import test from 'node:test';
import assert from 'node:assert/strict';
import { STEPS, VERSION, initialState, advance, back, restore, record } from '../public/flow.mjs';
test('advances only on a presenter action and caps at the closing step', () => { let s = initialState(); assert.equal(s.step,0); for (let i=0;i<20;i++) s=advance(s,'2026-10-25T17:00:00Z'); assert.equal(s.step,STEPS.length-1); assert.equal(s.events.length,STEPS.length-1); });
test('rewinding removes future markers and revisiting does not duplicate them', () => { let s=advance(advance(advance(initialState()))); s=back(s); assert.equal(s.step,2); assert.deepEqual(s.events.map(e=>e.step),[1,2]); s=advance(s); assert.deepEqual(s.events.map(e=>e.step),[1,2,3]); });
test('malformed and old persisted state safely reset', () => { for(const s of [null,{}, {version:VERSION,step:99,events:[]}, {version:'old',step:2,events:[]}]) assert.deepEqual(restore(s),initialState()); });
test('restored markers cannot supply injected narrative', () => { const s=restore({version:VERSION,step:1,events:[{step:1,at:'2026-10-25',text:'invented data'}]}); assert.equal(s.events[0].text,STEPS[1].event); });
test('export keeps the demo, model, sensor and measurement boundaries explicit', () => { const r=record(advance(initialState())); assert.equal(r.demo,true); assert.match(r.provenance.temperature,/not measured/); assert.match(r.provenance.chart,/not measured/); assert.match(r.provenance.gemini,/no live/); assert.match(r.hypothesis,/unverified/); });
