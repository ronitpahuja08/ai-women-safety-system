'use strict';
const el = id => document.getElementById(id);
let ticker = null, endTime = 0;
function displayTime(seconds) {
  const s = Math.max(0, seconds);
  return String(Math.floor(s / 60)).padStart(2,'0') + ':' + String(s % 60).padStart(2,'0');
}
async function checkMode() {
  try {
    const response = await fetch('/api/status', {cache:'no-store'});
    const data = await response.json();
    const labels = {
      configured: 'SMS provider configured',
      demo: 'DEMO MODE — NO SMS',
      misconfigured: 'SMS unavailable — check private server settings'
    };
    el('mode').textContent = labels[data.mode] || 'OFFLINE — NO SMS';
  } catch (_) { el('mode').textContent = 'OFFLINE — NO SMS'; }
}
async function getLocation() {
  if (!el('location').checked) return null;
  if (!navigator.geolocation) throw new Error('Location unavailable. Uncheck location and retry.');
  return new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(
    position => resolve({latitude: position.coords.latitude, longitude: position.coords.longitude}),
    () => reject(new Error('Location permission denied or timed out. Uncheck location and retry.')),
    {enableHighAccuracy:false, timeout:8000, maximumAge:0}
  ));
}
el('sos').addEventListener('click', async () => {
  const confirmText = 'Do you want to submit an SOS alert to the server? If SMS is configured, it will attempt to send to the preconfigured trusted contact. Delivery is not guaranteed.';
  if (!window.confirm(confirmText)) return;
  el('sos').disabled = true;
  el('result').textContent = 'Preparing your request…';
  try {
    const location = await getLocation();
    const response = await fetch('/api/alerts', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({confirm:true, location})});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Provider error');
    el('result').textContent = payload.status === 'demo_only'
      ? 'Demo complete. NO SMS or emergency service was contacted.'
      : 'SMS request submitted to provider. Delivery NOT confirmed. Please call trusted contacts directly if needed.';
  } catch (error) {
    el('result').textContent = 'Alert NOT confirmed: ' + error.message + '. Call emergency services directly if needed.';
  } finally { el('sos').disabled = false; }
});
function stop() { if (ticker !== null) clearInterval(ticker); ticker = null; }
el('start').addEventListener('click', () => {
  stop();
  endTime = Date.now() + Number(el('minutes').value) * 60000;
  function update() {
    const remaining = Math.max(0, Math.ceil((endTime-Date.now())/1000));
    el('timer').textContent = displayTime(remaining);
    if (!remaining) {
      stop(); el('timer').textContent = 'CHECK IN';
      window.alert('Check-in reminder: please contact your trusted person if appropriate.');
    }
  }
  update(); ticker = setInterval(update, 1000);
});
el('cancel').addEventListener('click', () => { stop(); el('timer').textContent = displayTime(Number(el('minutes').value)*60); });
el('minutes').addEventListener('change', () => {if (!ticker) el('timer').textContent=displayTime(Number(el('minutes').value)*60);});
checkMode();
