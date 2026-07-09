import { useRef, useState, useEffect } from 'react';

export default function SignaturePad({ onSave, saving }) {
  const canvasRef = useRef(null);
  const drawing = useRef(false);
  const [hasDrawn, setHasDrawn] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.strokeStyle = '#1a1a18';
  }, []);

  const getPos = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const point = e.touches ? e.touches[0] : e;
    return { x: point.clientX - rect.left, y: point.clientY - rect.top };
  };

  const start = (e) => {
    e.preventDefault();
    drawing.current = true;
    const { x, y } = getPos(e);
    const ctx = canvasRef.current.getContext('2d');
    ctx.beginPath();
    ctx.moveTo(x, y);
  };

  const move = (e) => {
    if (!drawing.current) return;
    e.preventDefault();
    const { x, y } = getPos(e);
    const ctx = canvasRef.current.getContext('2d');
    ctx.lineTo(x, y);
    ctx.stroke();
    setHasDrawn(true);
  };

  const end = () => { drawing.current = false; };

  const clear = () => {
    const canvas = canvasRef.current;
    canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
    setHasDrawn(false);
  };

  const save = () => {
    const dataUrl = canvasRef.current.toDataURL('image/png');
    onSave(dataUrl);
  };

  return (
    <div>
      <canvas
        ref={canvasRef}
        width={420}
        height={160}
        style={{ background: '#fff', border: '1px dashed #c9c8c2', borderRadius: 12, touchAction: 'none', cursor: 'crosshair', width: '100%', maxWidth: 420 }}
        onMouseDown={start}
        onMouseMove={move}
        onMouseUp={end}
        onMouseLeave={end}
        onTouchStart={start}
        onTouchMove={move}
        onTouchEnd={end}
      />
      <div style={{ display: 'flex', gap: 10, marginTop: 12 }}>
        <button type="button" onClick={clear} className="rx-btn-secondary">Clear</button>
        <button type="button" onClick={save} disabled={!hasDrawn || saving} className="rx-btn-primary">
          {saving ? 'Saving…' : 'Save signature'}
        </button>
      </div>
      <p style={{ fontSize: 13, color: '#8a8980', marginTop: 8 }}>
        Draw your signature above using your mouse, trackpad, or finger. It will be stamped on every prescription you issue.
      </p>
    </div>
  );
}
