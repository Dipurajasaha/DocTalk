import React from 'react';
import BackButton from '../../components/BackButton';

export default function PatientHistoryPanel({
  allergies = [],
  medications = [],
  conditions = [],
  vitals = {},
  surgeries = [],
  lifestyle = {},
  immunizations = [],
  familyHistory = [],
  healthView,
  setHealthView,
  medTab,
  setMedTab,
  vitalsForm,
  setVitalsForm,
  editingVitals,
  setEditingVitals,
  saveVitals,
  bmiCalc,
  lifestyleForm,
  setLifestyleForm,
  editingLifestyle,
  setEditingLifestyle,
  latestRx,
  appointments = [],
  setActivePanelFromNav,
  prescriptionApi,
  navigate
}) {
            const S = {
              card:   { background:'var(--bg-base)', borderRadius:'24px', padding:'20px 24px', boxShadow:'6px 6px 12px var(--shadow-dark), -6px -6px 12px var(--shadow-light)', border:'1px solid var(--border-subtle)' },
              label:  { fontSize:'11px', fontWeight:'700', color:'var(--text-secondary)', textTransform:'uppercase', letterSpacing:'0.5px', marginBottom:'4px', display:'block' },
              input:  { padding:'12px 16px', borderRadius:'9999px', border:'1px solid var(--border-subtle)', fontSize:'13px', outline:'none', width:'100%', boxSizing:'border-box', fontFamily:'inherit', background:'var(--bg-base)', boxShadow:'inset 4px 4px 8px var(--shadow-dark), inset -4px -4px 8px var(--shadow-light)' },
              select: { padding:'12px 16px', borderRadius:'9999px', border:'1px solid var(--border-subtle)', fontSize:'13px', outline:'none', width:'100%', boxSizing:'border-box', fontFamily:'inherit', background:'var(--bg-base)', boxShadow:'inset 4px 4px 8px var(--shadow-dark), inset -4px -4px 8px var(--shadow-light)' },
              addBtn: { padding:'10px 20px', background:'var(--accent-primary)', color:'#fff', border:'none', borderRadius:'50px', cursor:'pointer', fontWeight:'600', fontSize:'12px', display:'inline-flex', alignItems:'center', gap:'5px', transition:'all 0.2s ease', boxShadow:'4px 4px 10px rgba(124,92,255,0.3)' },
              cancelBtn: { padding:'10px 20px', borderRadius:'50px', border:'1px solid var(--border-subtle)', background:'var(--bg-base)', cursor:'pointer', fontSize:'12px', fontWeight:'600', color:'var(--text-secondary)', boxShadow:'4px 4px 10px var(--shadow-dark), -4px -4px 10px var(--shadow-light)' },
              saveBtn:   { padding:'10px 24px', borderRadius:'50px', background:'var(--accent-primary)', color:'#fff', border:'none', cursor:'pointer', fontSize:'12px', fontWeight:'600', boxShadow:'4px 4px 10px rgba(124,92,255,0.3)' },
              delBtn:    { padding:'6px 12px', borderRadius:'9999px', border:'none', background:'var(--bg-base)', cursor:'pointer', fontSize:'11px', color:'var(--accent-tertiary)', fontWeight:'600', boxShadow:'2px 2px 5px var(--shadow-dark), -2px -2px 5px var(--shadow-light)' },
              editBtn:   { padding:'6px 12px', borderRadius:'9999px', border:'none', background:'var(--bg-base)', cursor:'pointer', fontSize:'11px', color:'var(--accent-primary)', fontWeight:'600', boxShadow:'2px 2px 5px var(--shadow-dark), -2px -2px 5px var(--shadow-light)' },
            };
            const FG = ({ label, children }) => (
              <div style={{ display:'flex', flexDirection:'column', gap:'4px' }}>
                <span style={S.label}>{label}</span>
                {children}
              </div>
            );
            const severityColor  = { mild:'#22c55e', moderate:'#f59e0b', severe:'#ef4444', critical:'#7c3aed' };
            const statusColor    = { active:'#ef4444', resolved:'#22c55e', chronic:'#f97316', monitoring:'#3b82f6' };
            const statusBg       = { active:'#fef2f2', resolved:'#f0fdf4', chronic:'#fff7ed', monitoring:'#eff6ff' };
            const allergyColor   = { mild:'#22c55e', moderate:'#f59e0b', severe:'#ef4444', 'life-threatening':'#7c3aed' };

            const hasAlerts = allergies.filter(a=>a.severity==='severe'||a.severity==='life-threatening').length > 0;
            const currentMeds = medications.filter(m=>m.is_ongoing);
            const activeConditions = conditions.filter(c=>c.status==='active'||c.status==='chronic');

            const TABS = [
              { id:'overview',      label:'Overview',          icon:'🏠' },
              { id:'vitals',        label:'Vitals',            icon:'❤️' },
              { id:'conditions',    label:'Conditions',        icon:'🩺' },
              { id:'medications',   label:'Medications',       icon:'💊' },
              { id:'allergies',     label:'Allergies',         icon:'⚠️' },
              { id:'surgeries',     label:'Surgeries',         icon:'🔪' },
              { id:'family',        label:'Family History',    icon:'👨‍👩‍👧' },
              { id:'immunizations', label:'Immunisations',     icon:'💉' },
              { id:'lifestyle',     label:'Lifestyle',         icon:'🌿' },
            ];

            if (false) {
            return (
              <div style={{ display:'flex', flexDirection:'column', flex:1, minHeight:0, gap:'0' }}>
                {/* ── Page header ── */}
                <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'16px', flexShrink:0 }}>
                  <div>
                    <h2 style={{ margin:0, fontSize:'18px', color:'#6C5CE7', fontWeight:'800', letterSpacing:'-0.5px' }}>Medical Profile</h2>
                    <p style={{ margin:'3px 0 0', fontSize:'12px', color:'#8B7EFF' }}>Complete clinical record — visible to your treating doctors</p>
                  </div>
                  <div style={{ display:'flex', alignItems:'center', gap:'12px' }}>
                    <BackButton onClick={()=>setHealthView('dashboard')} label="Dashboard" style={{ marginBottom: 0 }} />
                    {hasAlerts && (
                      <div style={{ display:'flex', alignItems:'center', gap:'6px', background:'#fef2f2', border:'1px solid #fecaca', borderRadius:'8px', padding:'8px 14px' }}>
                        <span style={{ fontSize:'14px' }}>🚨</span>
                        <span style={{ fontSize:'12px', color:'#ef4444', fontWeight:'700' }}>Severe Allergy on Record</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* ── Tab bar ── */}
                <div style={{ display:'flex', gap:'4px', overflowX:'auto', flexShrink:0, paddingBottom:'2px', marginBottom:'16px', scrollbarWidth:'none' }}>
                  {TABS.map(t => (
                    <button key={t.id} onClick={() => setMedTab(t.id)}
                      style={{ padding:'8px 14px', borderRadius:'50px', border:'none', cursor:'pointer', fontSize:'12px', fontWeight:'600', whiteSpace:'nowrap', transition:'all 0.2s',
                        background: medTab===t.id ? '#6C5CE7' : '#F1F5F9',
                        color:      medTab===t.id ? '#fff'    : '#64748B',
                        boxShadow:  medTab===t.id ? '0 4px 12px rgba(108,92,231,0.3)' : 'none' }}>
                      {t.icon} {t.label}
                    </button>
                  ))}
                </div>

                <div style={{ flex:1, overflowY:'auto', display:'flex', flexDirection:'column', gap:'16px', minHeight:0 }}>

                  {/* ════════ OVERVIEW TAB ════════ */}
                  {medTab === 'overview' && (
                    <div style={{ display:'flex', flexDirection:'column', gap:'14px' }}>
                      {/* Alert bar */}
                      {hasAlerts && (
                        <div style={{ background:'#fef2f2', border:'1px solid #fecaca', borderRadius:'12px', padding:'14px 18px', display:'flex', alignItems:'flex-start', gap:'10px' }}>
                          <span style={{ fontSize:'18px', flexShrink:0 }}>🚨</span>
                          <div>
                            <div style={{ fontSize:'13px', fontWeight:'700', color:'#ef4444', marginBottom:'4px' }}>Critical Allergy Alert</div>
                            <div style={{ fontSize:'12px', color:'#ef4444' }}>
                              {allergies.filter(a=>a.severity==='severe'||a.severity==='life-threatening').map(a=>`${a.allergen} (${a.reaction})`).join(' · ')}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Quick-stats grid */}
                      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(150px,1fr))', gap:'12px' }}>
                        {[
                          { icon:'🩸', label:'Blood Group', value: vitals.blood_group || '—', color:'#ef4444' },
                          { icon:'📏', label:'Height / Weight', value: vitals.height && vitals.weight ? `${vitals.height}cm · ${vitals.weight}kg` : '—', color:'#3b82f6' },
                          { icon:'⚖️', label:'BMI', value: vitals.bmi || '—', color: parseFloat(vitals.bmi)>=25?'#f97316':'#22c55e' },
                          { icon:'💓', label:'Blood Pressure', value: vitals.blood_pressure || '—', color:'#8b5cf6' },
                          { icon:'🔵', label:'SpO₂', value: vitals.spo2 ? `${vitals.spo2}%` : '—', color:'#06b6d4' },
                          { icon:'🩺', label:'Active Conditions', value: activeConditions.length || '0', color:'#f97316' },
                          { icon:'💊', label:'Current Meds', value: currentMeds.length || '0', color:'#6C5CE7' },
                          { icon:'⚠️', label:'Known Allergies', value: allergies.length || '0', color: hasAlerts?'#ef4444':'#64748B' },
                        ].map(k => (
                          <div key={k.label} style={{ ...S.card, textAlign:'center', padding:'16px 12px' }}>
                            <div style={{ fontSize:'20px', marginBottom:'6px' }}>{k.icon}</div>
                            <div style={{ fontSize:'18px', fontWeight:'800', color:k.color, letterSpacing:'-0.5px' }}>{k.value}</div>
                            <div style={{ fontSize:'11px', color:'#94a3b8', marginTop:'3px', fontWeight:'500' }}>{k.label}</div>
                          </div>
                        ))}
                      </div>

                      {/* Active conditions + current meds side by side */}
                      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'14px' }}>
                        <div style={S.card}>
                          <div style={{ fontSize:'13px', fontWeight:'700', color:'#0f172a', marginBottom:'10px' }}>🩺 Active Conditions</div>
                          {activeConditions.length === 0 ? <p style={{ color:'#94a3b8', fontSize:'12px', margin:0 }}>None recorded</p> : activeConditions.map(c=>(
                            <div key={c.id} style={{ display:'flex', alignItems:'center', gap:'8px', padding:'6px 0', borderBottom:'1px solid #f1f5f9' }}>
                              <span style={{ width:'8px', height:'8px', borderRadius:'50%', background:statusColor[c.status]||'#6C5CE7', flexShrink:0, display:'inline-block' }}></span>
                              <span style={{ fontSize:'12px', fontWeight:'600', color:'#1e293b', flex:1 }}>{c.condition}</span>
                              {c.icd_code && <span style={{ fontSize:'10px', color:'#94a3b8', background:'#f1f5f9', padding:'2px 6px', borderRadius:'4px' }}>{c.icd_code}</span>}
                            </div>
                          ))}
                        </div>
                        <div style={S.card}>
                          <div style={{ fontSize:'13px', fontWeight:'700', color:'#0f172a', marginBottom:'10px' }}>💊 Current Medications</div>
                          {currentMeds.length === 0 ? <p style={{ color:'#94a3b8', fontSize:'12px', margin:0 }}>None recorded</p> : currentMeds.map(m=>(
                            <div key={m.id} style={{ padding:'6px 0', borderBottom:'1px solid #f1f5f9' }}>
                              <div style={{ fontSize:'12px', fontWeight:'700', color:'#1e293b' }}>{m.name}</div>
                              <div style={{ fontSize:'11px', color:'#64748B' }}>{m.dosage} · {m.frequency}</div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Allergies + Surgeries summary */}
                      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'14px' }}>
                        <div style={S.card}>
                          <div style={{ fontSize:'13px', fontWeight:'700', color:'#0f172a', marginBottom:'10px' }}>⚠️ Allergies</div>
                          {allergies.length === 0 ? <p style={{ color:'#94a3b8', fontSize:'12px', margin:0 }}>NKDA (No known drug allergies)</p> : allergies.map(a=>(
                            <div key={a.id} style={{ display:'flex', alignItems:'center', gap:'8px', padding:'5px 0', borderBottom:'1px solid #f1f5f9' }}>
                              <span style={{ fontSize:'11px', fontWeight:'700', padding:'2px 8px', borderRadius:'50px', background: a.severity==='severe'||a.severity==='life-threatening'?'#fef2f2':'#fff7ed', color:allergyColor[a.severity]||'#f97316' }}>{a.severity}</span>
                              <span style={{ fontSize:'12px', fontWeight:'600', color:'#1e293b' }}>{a.allergen}</span>
                              <span style={{ fontSize:'11px', color:'#94a3b8', marginLeft:'auto' }}>{a.reaction}</span>
                            </div>
                          ))}
                        </div>
                        <div style={S.card}>
                          <div style={{ fontSize:'13px', fontWeight:'700', color:'#0f172a', marginBottom:'10px' }}>🔪 Surgical History</div>
                          {surgeries.length === 0 ? <p style={{ color:'#94a3b8', fontSize:'12px', margin:0 }}>No surgeries recorded</p> : surgeries.map(s=>(
                            <div key={s.id} style={{ padding:'5px 0', borderBottom:'1px solid #f1f5f9' }}>
                              <div style={{ fontSize:'12px', fontWeight:'700', color:'#1e293b' }}>{s.procedure}</div>
                              <div style={{ fontSize:'11px', color:'#64748B' }}>{s.date ? new Date(s.date).toLocaleDateString('en-IN',{month:'short',year:'numeric'}) : ''}{s.hospital ? ` · ${s.hospital}` : ''}</div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Lifestyle snapshot */}
                      {(lifestyle.smoking !== 'never' || lifestyle.alcohol !== 'never' || lifestyle.exercise) && (
                        <div style={S.card}>
                          <div style={{ fontSize:'13px', fontWeight:'700', color:'#0f172a', marginBottom:'10px' }}>🌿 Lifestyle Snapshot</div>
                          <div style={{ display:'flex', flexWrap:'wrap', gap:'8px' }}>
                            {lifestyle.smoking !== 'never' && <span style={{ padding:'5px 12px', borderRadius:'50px', background:'#fef3c7', color:'#d97706', fontSize:'12px', fontWeight:'600' }}>🚬 Smoker ({lifestyle.smoking})</span>}
                            {lifestyle.alcohol !== 'never' && <span style={{ padding:'5px 12px', borderRadius:'50px', background:'#fef3c7', color:'#d97706', fontSize:'12px', fontWeight:'600' }}>🍺 Alcohol ({lifestyle.alcohol})</span>}
                            {lifestyle.exercise && lifestyle.exercise !== 'sedentary' && <span style={{ padding:'5px 12px', borderRadius:'50px', background:'#f0fdf4', color:'#16a34a', fontSize:'12px', fontWeight:'600' }}>🏃 {lifestyle.exercise} activity</span>}
                            {lifestyle.diet && <span style={{ padding:'5px 12px', borderRadius:'50px', background:'#eff6ff', color:'#2563eb', fontSize:'12px', fontWeight:'600' }}>🥗 {lifestyle.diet} diet</span>}
                            {lifestyle.occupation && <span style={{ padding:'5px 12px', borderRadius:'50px', background:'#f1f5f9', color:'#475569', fontSize:'12px', fontWeight:'600' }}>💼 {lifestyle.occupation}</span>}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* ════════ VITALS TAB ════════ */}
                  {medTab === 'vitals' && (
                    <div style={{ display:'flex', flexDirection:'column', gap:'14px' }}>
                      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                        <span style={{ fontSize:'14px', fontWeight:'700', color:'#0f172a' }}>Physical Measurements & Vitals</span>
                        <button style={S.addBtn} onClick={() => { setVitalsForm(vitals); setEditingVitals(true); }}>✏️ Edit Vitals</button>
                      </div>
                      {editingVitals ? (
                        <div style={S.card}>
                          <form onSubmit={e => { e.preventDefault(); const bmi = bmiCalc(vitalsForm.height, vitalsForm.weight); const v = {...vitalsForm, bmi}; saveVitals(v); setEditingVitals(false); }}>
                            <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:'14px 20px' }}>
                              {[
                                { label:'Height (cm)',           name:'height',               type:'number', placeholder:'e.g. 170' },
                                { label:'Weight (kg)',           name:'weight',               type:'number', placeholder:'e.g. 68' },
                                { label:'Blood Group',           name:'blood_group',           type:'select', options:['A+','A-','B+','B-','AB+','AB-','O+','O-'] },
                                { label:'Blood Pressure',        name:'blood_pressure',        type:'text',   placeholder:'e.g. 120/80' },
                                { label:'Heart Rate (bpm)',      name:'heart_rate',            type:'number', placeholder:'e.g. 72' },
                                { label:'SpO₂ (%)',              name:'spo2',                  type:'number', placeholder:'e.g. 98' },
                                { label:'Fasting Blood Sugar',   name:'blood_sugar_fasting',   type:'text',   placeholder:'e.g. 95 mg/dL' },
                                { label:'Post-Prandial Sugar',   name:'blood_sugar_pp',        type:'text',   placeholder:'e.g. 130 mg/dL' },
                                { label:'Temperature (°F)',      name:'temperature',           type:'number', placeholder:'e.g. 98.6' },
                              ].map(f => (
                                <FG key={f.name} label={f.label}>
                                  {f.type === 'select'
                                    ? <select style={S.select} value={vitalsForm[f.name]||''} onChange={e=>setVitalsForm(p=>({...p,[f.name]:e.target.value}))}>
                                        <option value="">— Select —</option>
                                        {f.options.map(o=><option key={o} value={o}>{o}</option>)}
                                      </select>
                                    : <input type={f.type} style={S.input} placeholder={f.placeholder} value={vitalsForm[f.name]||''} onChange={e=>setVitalsForm(p=>({...p,[f.name]:e.target.value}))} />
                                  }
                                </FG>
                              ))}
                              <div style={{ gridColumn:'span 3', display:'flex', gap:'10px', justifyContent:'flex-end', borderTop:'1px solid #f1f5f9', paddingTop:'14px', marginTop:'4px' }}>
                                <button type="button" style={S.cancelBtn} onClick={()=>setEditingVitals(false)}>Cancel</button>
                                <button type="submit" style={S.saveBtn}>Save Vitals</button>
                              </div>
                            </div>
                          </form>
                        </div>
                      ) : (
                        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(180px,1fr))', gap:'12px' }}>
                          {[
                            { icon:'📏', label:'Height', value: vitals.height ? `${vitals.height} cm` : '—' },
                            { icon:'⚖️', label:'Weight', value: vitals.weight ? `${vitals.weight} kg` : '—' },
                            { icon:'🧮', label:'BMI', value: vitals.bmi || (vitals.height&&vitals.weight ? bmiCalc(vitals.height,vitals.weight) : '—'), note: parseFloat(vitals.bmi||bmiCalc(vitals.height,vitals.weight))>=30?'Obese':parseFloat(vitals.bmi||bmiCalc(vitals.height,vitals.weight))>=25?'Overweight':parseFloat(vitals.bmi||bmiCalc(vitals.height,vitals.weight))>=18.5?'Normal':vitals.height?'Underweight':'' },
                            { icon:'🩸', label:'Blood Group', value: vitals.blood_group || '—' },
                            { icon:'💓', label:'Blood Pressure', value: vitals.blood_pressure || '—' },
                            { icon:'❤️', label:'Heart Rate', value: vitals.heart_rate ? `${vitals.heart_rate} bpm` : '—' },
                            { icon:'🔵', label:'SpO₂', value: vitals.spo2 ? `${vitals.spo2}%` : '—' },
                            { icon:'🌡️', label:'Temperature', value: vitals.temperature ? `${vitals.temperature}°F` : '—' },
                            { icon:'🍬', label:'Sugar (Fasting)', value: vitals.blood_sugar_fasting || '—' },
                            { icon:'🍬', label:'Sugar (PP)', value: vitals.blood_sugar_pp || '—' },
                          ].map(v => (
                            <div key={v.label} style={{ ...S.card, padding:'16px', textAlign:'center' }}>
                              <div style={{ fontSize:'22px', marginBottom:'6px' }}>{v.icon}</div>
                              <div style={{ fontSize:'17px', fontWeight:'800', color:'#0f172a', letterSpacing:'-0.3px' }}>{v.value}</div>
                              {v.note && <div style={{ fontSize:'10px', fontWeight:'700', color:'#f97316', marginTop:'2px' }}>{v.note}</div>}
                              <div style={{ fontSize:'11px', color:'#94a3b8', marginTop:'3px' }}>{v.label}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* ════════ CONDITIONS TAB ════════ */}
                  {medTab === 'conditions' && (
                    <div style={{ display:'flex', flexDirection:'column', gap:'12px' }}>
                      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                        <div style={{ display:'flex', gap:'6px', flexWrap:'wrap' }}>
                          {['all','active','chronic','resolved','monitoring'].map(f=>(
                            <button key={f} onClick={()=>setCondFilter(f)} style={{ padding:'5px 12px', borderRadius:'50px', border:'none', cursor:'pointer', fontSize:'11px', fontWeight:'600', background:condFilter===f?'#6C5CE7':'#F1F5F9', color:condFilter===f?'#fff':'#64748B' }}>{f.charAt(0).toUpperCase()+f.slice(1)}</button>
                          ))}
                        </div>
                        <button style={S.addBtn} onClick={()=>{setShowCondForm(true);setEditCondId(null);setCondForm({condition:'',icd_code:'',diagnosed_date:'',doctor_name:'',hospital:'',status:'active',severity:'moderate',is_hereditary:false,notes:''});}}>+ Add</button>
                      </div>
                      {showCondForm && (
                        <div style={S.card}>
                          <h4 style={{margin:'0 0 14px',fontSize:'14px',color:'#0f172a'}}>{editCondId?'Edit Condition':'New Condition'}</h4>
                          <form onSubmit={submitCondition}>
                            <div style={{ display:'grid', gridTemplateColumns:'repeat(2,1fr)', gap:'12px 18px' }}>
                              <FG label="Condition / Diagnosis *"><input required style={S.input} placeholder="e.g. Type 2 Diabetes Mellitus" value={condForm.condition} onChange={e=>setCondForm(p=>({...p,condition:e.target.value}))} /></FG>
                              <FG label="ICD-10 Code"><input style={S.input} placeholder="e.g. E11.9" value={condForm.icd_code} onChange={e=>setCondForm(p=>({...p,icd_code:e.target.value}))} /></FG>
                              <FG label="Date Diagnosed"><input type="date" style={S.input} value={condForm.diagnosed_date} onChange={e=>setCondForm(p=>({...p,diagnosed_date:e.target.value}))} /></FG>
                              <FG label="Treating Doctor"><input style={S.input} placeholder="Dr. Full Name" value={condForm.doctor_name} onChange={e=>setCondForm(p=>({...p,doctor_name:e.target.value}))} /></FG>
                              <FG label="Hospital / Clinic"><input style={S.input} placeholder="Hospital name" value={condForm.hospital} onChange={e=>setCondForm(p=>({...p,hospital:e.target.value}))} /></FG>
                              <FG label="Status"><select style={S.select} value={condForm.status} onChange={e=>setCondForm(p=>({...p,status:e.target.value}))}><option value="active">Active</option><option value="chronic">Chronic</option><option value="resolved">Resolved</option><option value="monitoring">Monitoring</option></select></FG>
                              <FG label="Severity"><select style={S.select} value={condForm.severity} onChange={e=>setCondForm(p=>({...p,severity:e.target.value}))}><option value="mild">Mild</option><option value="moderate">Moderate</option><option value="severe">Severe</option><option value="critical">Critical</option></select></FG>
                              <FG label="Hereditary?"><select style={S.select} value={condForm.is_hereditary} onChange={e=>setCondForm(p=>({...p,is_hereditary:e.target.value==='true'}))}><option value="false">No</option><option value="true">Yes</option></select></FG>
                              <div style={{gridColumn:'span 2'}}><FG label="Notes / Details"><input style={S.input} placeholder="Additional clinical notes" value={condForm.notes} onChange={e=>setCondForm(p=>({...p,notes:e.target.value}))} /></FG></div>
                              <div style={{gridColumn:'span 2',display:'flex',gap:'8px',justifyContent:'flex-end'}}>
                                <button type="button" style={S.cancelBtn} onClick={()=>{setShowCondForm(false);setEditCondId(null);}}>Cancel</button>
                                <button type="submit" style={S.saveBtn}>Save</button>
                              </div>
                            </div>
                          </form>
                        </div>
                      )}
                      {(condFilter==='all'?conditions:conditions.filter(c=>c.status===condFilter)).length===0
                        ? <div style={{textAlign:'center',padding:'40px',color:'#94a3b8',background:'#fff',borderRadius:'14px',border:'2px dashed #E2E8F0'}}><div style={{fontSize:'32px',marginBottom:'8px'}}>🩺</div>No conditions recorded.</div>
                        : (condFilter==='all'?conditions:conditions.filter(c=>c.status===condFilter)).map(c=>(
                          <div key={c.id} style={{...S.card,borderLeft:`4px solid ${statusColor[c.status]||'#6C5CE7'}`}}>
                            <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:'10px'}}>
                              <div style={{flex:1}}>
                                <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'8px',flexWrap:'wrap'}}>
                                  <span style={{fontSize:'14px',fontWeight:'700',color:'#0f172a'}}>{c.condition}</span>
                                  {c.icd_code&&<span style={{fontSize:'10px',background:'#f1f5f9',color:'#64748B',padding:'2px 8px',borderRadius:'4px',fontWeight:'600'}}>{c.icd_code}</span>}
                                  <span style={{fontSize:'10px',fontWeight:'700',padding:'2px 8px',borderRadius:'50px',background:statusBg[c.status]||'#f1f5f9',color:statusColor[c.status]||'#6C5CE7',textTransform:'uppercase'}}>{c.status}</span>
                                  <span style={{fontSize:'10px',fontWeight:'700',padding:'2px 8px',borderRadius:'50px',background:'#f8fafc',color:severityColor[c.severity]||'#64748B',textTransform:'uppercase'}}>{c.severity}</span>
                                  {c.is_hereditary&&<span style={{fontSize:'10px',fontWeight:'700',padding:'2px 8px',borderRadius:'50px',background:'#fdf4ff',color:'#9333ea'}}>Hereditary</span>}
                                </div>
                                <div style={{display:'flex',flexWrap:'wrap',gap:'12px'}}>
                                  {c.diagnosed_date&&<span style={{fontSize:'12px',color:'#64748B'}}>📅 {new Date(c.diagnosed_date).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})}</span>}
                                  {c.doctor_name&&<span style={{fontSize:'12px',color:'#64748B'}}>👨‍⚕️ Dr. {c.doctor_name}</span>}
                                  {c.hospital&&<span style={{fontSize:'12px',color:'#64748B'}}>🏥 {c.hospital}</span>}
                                </div>
                                {c.notes&&<p style={{margin:'6px 0 0',fontSize:'12px',color:'#94a3b8',fontStyle:'italic'}}>{c.notes}</p>}
                              </div>
                              <div style={{display:'flex',gap:'5px',flexShrink:0}}>
                                <button style={S.editBtn} onClick={()=>{setCondForm({...c});setEditCondId(c.id);setShowCondForm(true);}}>Edit</button>
                                <button style={S.delBtn} onClick={()=>{if(window.confirm('Delete?'))saveConditions(conditions.filter(x=>x.id!==c.id));}}>✕</button>
                              </div>
                            </div>
                          </div>
                        ))
                      }
                    </div>
                  )}

                  {/* ════════ MEDICATIONS TAB ════════ */}
                  {medTab === 'medications' && (
                    <div style={{display:'flex',flexDirection:'column',gap:'12px'}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                        <span style={{fontSize:'13px',color:'#64748B'}}>{currentMeds.length} active · {medications.filter(m=>!m.is_ongoing).length} past</span>
                        <button style={S.addBtn} onClick={()=>{setShowMedForm(true);setEditMedId(null);setMedForm({name:'',dosage:'',frequency:'',route:'oral',prescribed_by:'',prescribed_date:'',start_date:'',end_date:'',reason:'',is_ongoing:true,side_effects:'',notes:''});}}>+ Add</button>
                      </div>
                      {showMedForm&&(
                        <div style={S.card}>
                          <h4 style={{margin:'0 0 14px',fontSize:'14px',color:'#0f172a'}}>{editMedId?'Edit Medication':'New Medication'}</h4>
                          <form onSubmit={submitMedication}>
                            <div style={{display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:'12px 18px'}}>
                              <FG label="Drug Name *"><input required style={S.input} placeholder="e.g. Metformin" value={medForm.name} onChange={e=>setMedForm(p=>({...p,name:e.target.value}))} /></FG>
                              <FG label="Dosage"><input style={S.input} placeholder="e.g. 500mg" value={medForm.dosage} onChange={e=>setMedForm(p=>({...p,dosage:e.target.value}))} /></FG>
                              <FG label="Frequency"><input style={S.input} placeholder="e.g. Twice daily after meals" value={medForm.frequency} onChange={e=>setMedForm(p=>({...p,frequency:e.target.value}))} /></FG>
                              <FG label="Route"><select style={S.select} value={medForm.route} onChange={e=>setMedForm(p=>({...p,route:e.target.value}))}>
                                {['oral','intravenous','intramuscular','topical','sublingual','inhalation','subcutaneous','other'].map(r=><option key={r} value={r}>{r.charAt(0).toUpperCase()+r.slice(1)}</option>)}
                              </select></FG>
                              <FG label="Prescribed By"><input style={S.input} placeholder="Dr. Name" value={medForm.prescribed_by} onChange={e=>setMedForm(p=>({...p,prescribed_by:e.target.value}))} /></FG>
                              <FG label="Reason / Indication"><input style={S.input} placeholder="e.g. Type 2 Diabetes" value={medForm.reason} onChange={e=>setMedForm(p=>({...p,reason:e.target.value}))} /></FG>
                              <FG label="Start Date"><input type="date" style={S.input} value={medForm.start_date} onChange={e=>setMedForm(p=>({...p,start_date:e.target.value}))} /></FG>
                              <FG label="End Date"><input type="date" style={S.input} value={medForm.end_date} onChange={e=>setMedForm(p=>({...p,end_date:e.target.value}))} /></FG>
                              <FG label="Known Side Effects"><input style={S.input} placeholder="e.g. Nausea, dizziness" value={medForm.side_effects} onChange={e=>setMedForm(p=>({...p,side_effects:e.target.value}))} /></FG>
                              <FG label="Ongoing?"><select style={S.select} value={medForm.is_ongoing} onChange={e=>setMedForm(p=>({...p,is_ongoing:e.target.value==='true'}))}>
                                <option value="true">Yes (current)</option><option value="false">No (stopped)</option>
                              </select></FG>
                              <div style={{gridColumn:'span 2',display:'flex',gap:'8px',justifyContent:'flex-end'}}>
                                <button type="button" style={S.cancelBtn} onClick={()=>{setShowMedForm(false);setEditMedId(null);}}>Cancel</button>
                                <button type="submit" style={S.saveBtn}>Save</button>
                              </div>
                            </div>
                          </form>
                        </div>
                      )}
                      {medications.length===0
                        ? <div style={{textAlign:'center',padding:'40px',color:'#94a3b8',background:'#fff',borderRadius:'14px',border:'2px dashed #E2E8F0'}}><div style={{fontSize:'32px',marginBottom:'8px'}}>💊</div>No medications logged.</div>
                        : medications.map(m=>(
                          <div key={m.id} style={{...S.card,borderLeft:`4px solid ${m.is_ongoing?'#6C5CE7':'#94a3b8'}`}}>
                            <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:'10px'}}>
                              <div style={{flex:1}}>
                                <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'6px',flexWrap:'wrap'}}>
                                  <span style={{fontSize:'14px',fontWeight:'700',color:'#0f172a'}}>{m.name}</span>
                                  {m.dosage&&<span style={{fontSize:'12px',color:'#6C5CE7',fontWeight:'600',background:'#EDE9FE',padding:'2px 8px',borderRadius:'4px'}}>{m.dosage}</span>}
                                  <span style={{fontSize:'10px',fontWeight:'700',padding:'2px 8px',borderRadius:'50px',background:m.is_ongoing?'#f0fdf4':'#f1f5f9',color:m.is_ongoing?'#16a34a':'#94a3b8',textTransform:'uppercase'}}>{m.is_ongoing?'Current':'Stopped'}</span>
                                  {m.route&&<span style={{fontSize:'10px',color:'#64748B',background:'#f8fafc',padding:'2px 8px',borderRadius:'4px',textTransform:'capitalize'}}>{m.route}</span>}
                                </div>
                                <div style={{display:'flex',flexWrap:'wrap',gap:'10px'}}>
                                  {m.frequency&&<span style={{fontSize:'12px',color:'#64748B'}}>🕐 {m.frequency}</span>}
                                  {m.reason&&<span style={{fontSize:'12px',color:'#64748B'}}>📋 For: {m.reason}</span>}
                                  {m.prescribed_by&&<span style={{fontSize:'12px',color:'#64748B'}}>👨‍⚕️ Dr. {m.prescribed_by}</span>}
                                  {m.start_date&&<span style={{fontSize:'12px',color:'#64748B'}}>📅 Since {new Date(m.start_date).toLocaleDateString('en-IN',{month:'short',year:'numeric'})}</span>}
                                </div>
                                {m.side_effects&&<p style={{margin:'5px 0 0',fontSize:'12px',color:'#f97316'}}>⚠️ Side effects: {m.side_effects}</p>}
                              </div>
                              <div style={{display:'flex',gap:'5px',flexShrink:0}}>
                                <button style={S.editBtn} onClick={()=>{setMedForm({...m});setEditMedId(m.id);setShowMedForm(true);}}>Edit</button>
                                <button style={S.delBtn} onClick={()=>{if(window.confirm('Delete?'))saveMedications(medications.filter(x=>x.id!==m.id));}}>✕</button>
                              </div>
                            </div>
                          </div>
                        ))
                      }
                    </div>
                  )}

                  {/* ════════ ALLERGIES TAB ════════ */}
                  {medTab === 'allergies' && (
                    <div style={{display:'flex',flexDirection:'column',gap:'12px'}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                        <span style={{fontSize:'13px',color: hasAlerts?'#ef4444':'#64748B',fontWeight: hasAlerts?'700':'400'}}>{hasAlerts?'⚠️ Severe allergy on record':'All allergies'}</span>
                        <button style={S.addBtn} onClick={()=>{setShowAllergyForm(true);setEditAllergyId(null);setAllergyForm({allergen:'',type:'drug',reaction:'',severity:'moderate',onset_date:'',notes:''});}}>+ Add</button>
                      </div>
                      {showAllergyForm&&(
                        <div style={S.card}>
                          <h4 style={{margin:'0 0 14px',fontSize:'14px',color:'#0f172a'}}>{editAllergyId?'Edit Allergy':'New Allergy'}</h4>
                          <form onSubmit={submitAllergy}>
                            <div style={{display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:'12px 18px'}}>
                              <FG label="Allergen *"><input required style={S.input} placeholder="e.g. Penicillin / Peanuts / Dust" value={allergyForm.allergen} onChange={e=>setAllergyForm(p=>({...p,allergen:e.target.value}))} /></FG>
                              <FG label="Type"><select style={S.select} value={allergyForm.type} onChange={e=>setAllergyForm(p=>({...p,type:e.target.value}))}>
                                {['drug','food','environmental','insect','latex','chemical','other'].map(t=><option key={t} value={t}>{t.charAt(0).toUpperCase()+t.slice(1)}</option>)}
                              </select></FG>
                              <FG label="Reaction / Symptoms"><input style={S.input} placeholder="e.g. Anaphylaxis, Hives, Swelling" value={allergyForm.reaction} onChange={e=>setAllergyForm(p=>({...p,reaction:e.target.value}))} /></FG>
                              <FG label="Severity"><select style={S.select} value={allergyForm.severity} onChange={e=>setAllergyForm(p=>({...p,severity:e.target.value}))}>
                                <option value="mild">Mild</option><option value="moderate">Moderate</option><option value="severe">Severe</option><option value="life-threatening">Life-threatening / Anaphylaxis</option>
                              </select></FG>
                              <FG label="First Onset Date"><input type="date" style={S.input} value={allergyForm.onset_date} onChange={e=>setAllergyForm(p=>({...p,onset_date:e.target.value}))} /></FG>
                              <FG label="Notes"><input style={S.input} placeholder="e.g. Carry EpiPen" value={allergyForm.notes} onChange={e=>setAllergyForm(p=>({...p,notes:e.target.value}))} /></FG>
                              <div style={{gridColumn:'span 2',display:'flex',gap:'8px',justifyContent:'flex-end'}}>
                                <button type="button" style={S.cancelBtn} onClick={()=>{setShowAllergyForm(false);setEditAllergyId(null);}}>Cancel</button>
                                <button type="submit" style={S.saveBtn}>Save</button>
                              </div>
                            </div>
                          </form>
                        </div>
                      )}
                      {allergies.length===0
                        ? <div style={{...S.card,textAlign:'center',padding:'32px',color:'#22c55e',fontWeight:'700',fontSize:'14px'}}>✅ NKDA — No Known Drug Allergies</div>
                        : allergies.map(a=>(
                          <div key={a.id} style={{...S.card,borderLeft:`4px solid ${allergyColor[a.severity]||'#f97316'}`}}>
                            <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:'10px'}}>
                              <div style={{flex:1}}>
                                <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'6px',flexWrap:'wrap'}}>
                                  <span style={{fontSize:'14px',fontWeight:'700',color:'#0f172a'}}>{a.allergen}</span>
                                  <span style={{fontSize:'10px',fontWeight:'700',padding:'2px 8px',borderRadius:'50px',background: a.severity==='life-threatening'?'#fdf4ff':a.severity==='severe'?'#fef2f2':'#fff7ed',color:allergyColor[a.severity]||'#f97316',textTransform:'uppercase'}}>{a.severity}</span>
                                  <span style={{fontSize:'10px',color:'#64748B',background:'#f1f5f9',padding:'2px 8px',borderRadius:'4px',textTransform:'capitalize'}}>{a.type}</span>
                                </div>
                                <div style={{display:'flex',flexWrap:'wrap',gap:'10px'}}>
                                  {a.reaction&&<span style={{fontSize:'12px',color:'#64748B'}}>🤒 Reaction: {a.reaction}</span>}
                                  {a.onset_date&&<span style={{fontSize:'12px',color:'#64748B'}}>📅 Since {new Date(a.onset_date).toLocaleDateString('en-IN',{month:'short',year:'numeric'})}</span>}
                                </div>
                                {a.notes&&<p style={{margin:'5px 0 0',fontSize:'12px',color:'#94a3b8',fontStyle:'italic'}}>{a.notes}</p>}
                              </div>
                              <div style={{display:'flex',gap:'5px',flexShrink:0}}>
                                <button style={S.editBtn} onClick={()=>{setAllergyForm({...a});setEditAllergyId(a.id);setShowAllergyForm(true);}}>Edit</button>
                                <button style={S.delBtn} onClick={()=>{if(window.confirm('Delete?'))saveAllergies(allergies.filter(x=>x.id!==a.id));}}>✕</button>
                              </div>
                            </div>
                          </div>
                        ))
                      }
                    </div>
                  )}

                  {/* ════════ SURGERIES TAB ════════ */}
                  {medTab === 'surgeries' && (
                    <div style={{display:'flex',flexDirection:'column',gap:'12px'}}>
                      <div style={{display:'flex',justifyContent:'flex-end'}}>
                        <button style={S.addBtn} onClick={()=>{setShowSurgForm(true);setEditSurgId(null);setSurgForm({procedure:'',date:'',surgeon:'',hospital:'',anesthesia:'general',outcome:'successful',complications:'',notes:''});}}>+ Add</button>
                      </div>
                      {showSurgForm&&(
                        <div style={S.card}>
                          <h4 style={{margin:'0 0 14px',fontSize:'14px',color:'#0f172a'}}>{editSurgId?'Edit Surgery':'New Surgical Record'}</h4>
                          <form onSubmit={submitSurgery}>
                            <div style={{display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:'12px 18px'}}>
                              <FG label="Procedure / Surgery *"><input required style={S.input} placeholder="e.g. Appendectomy" value={surgForm.procedure} onChange={e=>setSurgForm(p=>({...p,procedure:e.target.value}))} /></FG>
                              <FG label="Date"><input type="date" style={S.input} value={surgForm.date} onChange={e=>setSurgForm(p=>({...p,date:e.target.value}))} /></FG>
                              <FG label="Surgeon"><input style={S.input} placeholder="Dr. Name" value={surgForm.surgeon} onChange={e=>setSurgForm(p=>({...p,surgeon:e.target.value}))} /></FG>
                              <FG label="Hospital"><input style={S.input} placeholder="Hospital name" value={surgForm.hospital} onChange={e=>setSurgForm(p=>({...p,hospital:e.target.value}))} /></FG>
                              <FG label="Anaesthesia"><select style={S.select} value={surgForm.anesthesia} onChange={e=>setSurgForm(p=>({...p,anesthesia:e.target.value}))}>
                                {['general','local','regional','spinal','epidural','sedation','none'].map(a=><option key={a} value={a}>{a.charAt(0).toUpperCase()+a.slice(1)}</option>)}
                              </select></FG>
                              <FG label="Outcome"><select style={S.select} value={surgForm.outcome} onChange={e=>setSurgForm(p=>({...p,outcome:e.target.value}))}>
                                {['successful','complicated','ongoing','unknown'].map(o=><option key={o} value={o}>{o.charAt(0).toUpperCase()+o.slice(1)}</option>)}
                              </select></FG>
                              <div style={{gridColumn:'span 2'}}><FG label="Complications (if any)"><input style={S.input} placeholder="e.g. Post-op infection, bleeding" value={surgForm.complications} onChange={e=>setSurgForm(p=>({...p,complications:e.target.value}))} /></FG></div>
                              <div style={{gridColumn:'span 2'}}><FG label="Notes"><input style={S.input} value={surgForm.notes} onChange={e=>setSurgForm(p=>({...p,notes:e.target.value}))} /></FG></div>
                              <div style={{gridColumn:'span 2',display:'flex',gap:'8px',justifyContent:'flex-end'}}>
                                <button type="button" style={S.cancelBtn} onClick={()=>{setShowSurgForm(false);setEditSurgId(null);}}>Cancel</button>
                                <button type="submit" style={S.saveBtn}>Save</button>
                              </div>
                            </div>
                          </form>
                        </div>
                      )}
                      {surgeries.length===0
                        ? <div style={{textAlign:'center',padding:'40px',color:'#94a3b8',background:'#fff',borderRadius:'14px',border:'2px dashed #E2E8F0'}}><div style={{fontSize:'32px',marginBottom:'8px'}}>🔪</div>No surgeries recorded.</div>
                        : surgeries.map(s=>(
                          <div key={s.id} style={{...S.card,borderLeft:`4px solid ${s.outcome==='successful'?'#22c55e':s.outcome==='complicated'?'#ef4444':'#94a3b8'}`}}>
                            <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:'10px'}}>
                              <div style={{flex:1}}>
                                <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'6px',flexWrap:'wrap'}}>
                                  <span style={{fontSize:'14px',fontWeight:'700',color:'#0f172a'}}>{s.procedure}</span>
                                  <span style={{fontSize:'10px',fontWeight:'700',padding:'2px 8px',borderRadius:'50px',background:s.outcome==='successful'?'#f0fdf4':'#fef2f2',color:s.outcome==='successful'?'#16a34a':'#ef4444',textTransform:'capitalize'}}>{s.outcome}</span>
                                  <span style={{fontSize:'10px',color:'#64748B',background:'#f1f5f9',padding:'2px 8px',borderRadius:'4px',textTransform:'capitalize'}}>{s.anesthesia} anaesthesia</span>
                                </div>
                                <div style={{display:'flex',flexWrap:'wrap',gap:'10px'}}>
                                  {s.date&&<span style={{fontSize:'12px',color:'#64748B'}}>📅 {new Date(s.date).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})}</span>}
                                  {s.surgeon&&<span style={{fontSize:'12px',color:'#64748B'}}>👨‍⚕️ Dr. {s.surgeon}</span>}
                                  {s.hospital&&<span style={{fontSize:'12px',color:'#64748B'}}>🏥 {s.hospital}</span>}
                                </div>
                                {s.complications&&<p style={{margin:'5px 0 0',fontSize:'12px',color:'#ef4444'}}>⚠️ Complications: {s.complications}</p>}
                                {s.notes&&<p style={{margin:'3px 0 0',fontSize:'12px',color:'#94a3b8',fontStyle:'italic'}}>{s.notes}</p>}
                              </div>
                              <div style={{display:'flex',gap:'5px',flexShrink:0}}>
                                <button style={S.editBtn} onClick={()=>{setSurgForm({...s});setEditSurgId(s.id);setShowSurgForm(true);}}>Edit</button>
                                <button style={S.delBtn} onClick={()=>{if(window.confirm('Delete?'))saveSurgeries(surgeries.filter(x=>x.id!==s.id));}}>✕</button>
                              </div>
                            </div>
                          </div>
                        ))
                      }
                    </div>
                  )}

                  {/* ════════ FAMILY HISTORY TAB ════════ */}
                  {medTab === 'family' && (
                    <div style={{display:'flex',flexDirection:'column',gap:'12px'}}>
                      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
                        <p style={{margin:0,fontSize:'12px',color:'#94a3b8'}}>Hereditary conditions inform risk assessment for the patient and their doctor.</p>
                        <button style={S.addBtn} onClick={()=>{setShowFamForm(true);setEditFamId(null);setFamForm({relation:'',condition:'',age_of_onset:'',deceased:false,notes:''});}}>+ Add</button>
                      </div>
                      {showFamForm&&(
                        <div style={S.card}>
                          <h4 style={{margin:'0 0 14px',fontSize:'14px',color:'#0f172a'}}>{editFamId?'Edit Entry':'Family History Entry'}</h4>
                          <form onSubmit={submitFamily}>
                            <div style={{display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:'12px 18px'}}>
                              <FG label="Relation *"><select required style={S.select} value={famForm.relation} onChange={e=>setFamForm(p=>({...p,relation:e.target.value}))}>
                                <option value="">— Select —</option>
                                {['Father','Mother','Paternal Grandfather','Paternal Grandmother','Maternal Grandfather','Maternal Grandmother','Brother','Sister','Son','Daughter','Uncle','Aunt'].map(r=><option key={r} value={r}>{r}</option>)}
                              </select></FG>
                              <FG label="Condition *"><input required style={S.input} placeholder="e.g. Hypertension, Diabetes" value={famForm.condition} onChange={e=>setFamForm(p=>({...p,condition:e.target.value}))} /></FG>
                              <FG label="Age of Onset"><input type="number" style={S.input} placeholder="Age in years" value={famForm.age_of_onset} onChange={e=>setFamForm(p=>({...p,age_of_onset:e.target.value}))} /></FG>
                              <FG label="Status"><select style={S.select} value={famForm.deceased} onChange={e=>setFamForm(p=>({...p,deceased:e.target.value==='true'}))}>
                                <option value="false">Alive</option><option value="true">Deceased</option>
                              </select></FG>
                              <div style={{gridColumn:'span 2'}}><FG label="Notes"><input style={S.input} placeholder="Any relevant detail" value={famForm.notes} onChange={e=>setFamForm(p=>({...p,notes:e.target.value}))} /></FG></div>
                              <div style={{gridColumn:'span 2',display:'flex',gap:'8px',justifyContent:'flex-end'}}>
                                <button type="button" style={S.cancelBtn} onClick={()=>{setShowFamForm(false);setEditFamId(null);}}>Cancel</button>
                                <button type="submit" style={S.saveBtn}>Save</button>
                              </div>
                            </div>
                          </form>
                        </div>
                      )}
                      {familyHistory.length===0
                        ? <div style={{textAlign:'center',padding:'40px',color:'#94a3b8',background:'#fff',borderRadius:'14px',border:'2px dashed #E2E8F0'}}><div style={{fontSize:'32px',marginBottom:'8px'}}>👨‍👩‍👧</div>No family history recorded.</div>
                        : (
                          <div style={{overflowX:'auto'}}>
                            <table style={{width:'100%',borderCollapse:'collapse',fontSize:'13px',background:'#fff',borderRadius:'14px',overflow:'hidden'}}>
                              <thead><tr style={{background:'#f8fafc'}}>
                                {['Relation','Condition','Age of Onset','Status','Notes',''].map(h=><th key={h} style={{padding:'10px 14px',textAlign:'left',fontSize:'11px',fontWeight:'700',color:'#64748B',letterSpacing:'0.5px',textTransform:'uppercase',borderBottom:'1px solid #E2E8F0'}}>{h}</th>)}
                              </tr></thead>
                              <tbody>
                                {familyHistory.map(f=>(
                                  <tr key={f.id} style={{borderBottom:'1px solid #f1f5f9'}}>
                                    <td style={{padding:'10px 14px',fontWeight:'600',color:'#1e293b'}}>{f.relation}</td>
                                    <td style={{padding:'10px 14px',color:'#334155'}}>{f.condition}</td>
                                    <td style={{padding:'10px 14px',color:'#64748B'}}>{f.age_of_onset ? `~${f.age_of_onset} yrs` : '—'}</td>
                                    <td style={{padding:'10px 14px'}}><span style={{padding:'3px 8px',borderRadius:'50px',fontSize:'10px',fontWeight:'700',background:f.deceased?'#fef2f2':'#f0fdf4',color:f.deceased?'#ef4444':'#16a34a'}}>{f.deceased?'Deceased':'Alive'}</span></td>
                                    <td style={{padding:'10px 14px',color:'#94a3b8',fontSize:'12px',fontStyle:'italic'}}>{f.notes||'—'}</td>
                                    <td style={{padding:'10px 14px'}}>
                                      <div style={{display:'flex',gap:'4px'}}>
                                        <button style={S.editBtn} onClick={()=>{setFamForm({...f});setEditFamId(f.id);setShowFamForm(true);}}>Edit</button>
                                        <button style={S.delBtn} onClick={()=>{if(window.confirm('Delete?'))saveFamilyHistory(familyHistory.filter(x=>x.id!==f.id));}}>✕</button>
                                      </div>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )
                      }
                    </div>
                  )}

                  {/* ════════ IMMUNIZATIONS TAB ════════ */}
                  {medTab === 'immunizations' && (
                    <div style={{display:'flex',flexDirection:'column',gap:'12px'}}>
                      <div style={{display:'flex',justifyContent:'flex-end'}}>
                        <button style={S.addBtn} onClick={()=>{setShowImmuForm(true);setEditImmuId(null);setImmuForm({vaccine:'',date_given:'',dose:'',administered_by:'',next_due:'',notes:''});}}>+ Add</button>
                      </div>
                      {showImmuForm&&(
                        <div style={S.card}>
                          <h4 style={{margin:'0 0 14px',fontSize:'14px',color:'#0f172a'}}>{editImmuId?'Edit Record':'Add Immunisation'}</h4>
                          <form onSubmit={submitImmunization}>
                            <div style={{display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:'12px 18px'}}>
                              <FG label="Vaccine Name *"><input required style={S.input} placeholder="e.g. COVID-19 Booster / Flu / Hepatitis B" value={immuForm.vaccine} onChange={e=>setImmuForm(p=>({...p,vaccine:e.target.value}))} /></FG>
                              <FG label="Dose Number / Type"><input style={S.input} placeholder="e.g. Dose 2 / Booster" value={immuForm.dose} onChange={e=>setImmuForm(p=>({...p,dose:e.target.value}))} /></FG>
                              <FG label="Date Given"><input type="date" style={S.input} value={immuForm.date_given} onChange={e=>setImmuForm(p=>({...p,date_given:e.target.value}))} /></FG>
                              <FG label="Next Due Date"><input type="date" style={S.input} value={immuForm.next_due} onChange={e=>setImmuForm(p=>({...p,next_due:e.target.value}))} /></FG>
                              <FG label="Administered By"><input style={S.input} placeholder="Doctor / Clinic" value={immuForm.administered_by} onChange={e=>setImmuForm(p=>({...p,administered_by:e.target.value}))} /></FG>
                              <FG label="Notes"><input style={S.input} placeholder="Batch no., reactions, etc." value={immuForm.notes} onChange={e=>setImmuForm(p=>({...p,notes:e.target.value}))} /></FG>
                              <div style={{gridColumn:'span 2',display:'flex',gap:'8px',justifyContent:'flex-end'}}>
                                <button type="button" style={S.cancelBtn} onClick={()=>{setShowImmuForm(false);setEditImmuId(null);}}>Cancel</button>
                                <button type="submit" style={S.saveBtn}>Save</button>
                              </div>
                            </div>
                          </form>
                        </div>
                      )}
                      {immunizations.length===0
                        ? <div style={{textAlign:'center',padding:'40px',color:'#94a3b8',background:'#fff',borderRadius:'14px',border:'2px dashed #E2E8F0'}}><div style={{fontSize:'32px',marginBottom:'8px'}}>💉</div>No immunisation records added.</div>
                        : immunizations.map(i=>{
                          const isDue = i.next_due && new Date(i.next_due) <= new Date();
                          return (
                            <div key={i.id} style={{...S.card,borderLeft:`4px solid ${isDue?'#ef4444':'#22c55e'}`}}>
                              <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:'10px'}}>
                                <div style={{flex:1}}>
                                  <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'6px',flexWrap:'wrap'}}>
                                    <span style={{fontSize:'14px',fontWeight:'700',color:'#0f172a'}}>{i.vaccine}</span>
                                    {i.dose&&<span style={{fontSize:'11px',color:'#6C5CE7',background:'#EDE9FE',padding:'2px 8px',borderRadius:'4px',fontWeight:'600'}}>{i.dose}</span>}
                                    {isDue&&<span style={{fontSize:'10px',fontWeight:'700',padding:'2px 8px',borderRadius:'50px',background:'#fef2f2',color:'#ef4444'}}>⏰ Due / Overdue</span>}
                                  </div>
                                  <div style={{display:'flex',flexWrap:'wrap',gap:'10px'}}>
                                    {i.date_given&&<span style={{fontSize:'12px',color:'#64748B'}}>💉 Given: {new Date(i.date_given).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})}</span>}
                                    {i.next_due&&<span style={{fontSize:'12px',color:isDue?'#ef4444':'#64748B'}}>🔔 Next due: {new Date(i.next_due).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})}</span>}
                                    {i.administered_by&&<span style={{fontSize:'12px',color:'#64748B'}}>👨‍⚕️ {i.administered_by}</span>}
                                  </div>
                                  {i.notes&&<p style={{margin:'5px 0 0',fontSize:'12px',color:'#94a3b8',fontStyle:'italic'}}>{i.notes}</p>}
                                </div>
                                <div style={{display:'flex',gap:'5px',flexShrink:0}}>
                                  <button style={S.editBtn} onClick={()=>{setImmuForm({...i});setEditImmuId(i.id);setShowImmuForm(true);}}>Edit</button>
                                  <button style={S.delBtn} onClick={()=>{if(window.confirm('Delete?'))saveImmunizations(immunizations.filter(x=>x.id!==i.id));}}>✕</button>
                                </div>
                              </div>
                            </div>
                          );
                        })
                      }
                    </div>
                  )}

                  {/* ════════ LIFESTYLE TAB ════════ */}
                  {medTab === 'lifestyle' && (
                    <div style={{display:'flex',flexDirection:'column',gap:'14px'}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                        <span style={{fontSize:'13px',color:'#64748B'}}>Lifestyle factors are clinically relevant for diagnosis and treatment planning.</span>
                        <button style={S.addBtn} onClick={()=>{setLifestyleForm(lifestyle);setEditingLifestyle(true);}}>✏️ Edit</button>
                      </div>
                      {editingLifestyle ? (
                        <div style={S.card}>
                          <form onSubmit={e=>{e.preventDefault();saveLifestyle(lifestyleForm);setEditingLifestyle(false);}}>
                            <div style={{display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:'14px 20px'}}>
                              <FG label="Smoking Status"><select style={S.select} value={lifestyleForm.smoking} onChange={e=>setLifestyleForm(p=>({...p,smoking:e.target.value}))}>
                                {['never','ex-smoker','occasional','current'].map(v=><option key={v} value={v}>{v.charAt(0).toUpperCase()+v.slice(1)}</option>)}
                              </select></FG>
                              {lifestyleForm.smoking!=='never'&&<>
                                <FG label="Packs/day"><input type="number" style={S.input} placeholder="e.g. 0.5" value={lifestyleForm.smoking_packs_per_day} onChange={e=>setLifestyleForm(p=>({...p,smoking_packs_per_day:e.target.value}))} /></FG>
                                <FG label="Years smoked"><input type="number" style={S.input} placeholder="e.g. 10" value={lifestyleForm.smoking_years} onChange={e=>setLifestyleForm(p=>({...p,smoking_years:e.target.value}))} /></FG>
                              </>}
                              <FG label="Alcohol Use"><select style={S.select} value={lifestyleForm.alcohol} onChange={e=>setLifestyleForm(p=>({...p,alcohol:e.target.value}))}>
                                {['never','social','occasional','moderate','heavy'].map(v=><option key={v} value={v}>{v.charAt(0).toUpperCase()+v.slice(1)}</option>)}
                              </select></FG>
                              {lifestyleForm.alcohol!=='never'&&<FG label="Units/week"><input type="number" style={S.input} placeholder="e.g. 7" value={lifestyleForm.alcohol_units_per_week} onChange={e=>setLifestyleForm(p=>({...p,alcohol_units_per_week:e.target.value}))} /></FG>}
                              <FG label="Tobacco Chewing"><select style={S.select} value={lifestyleForm.tobacco_chewing} onChange={e=>setLifestyleForm(p=>({...p,tobacco_chewing:e.target.value==='true'}))}>
                                <option value="false">No</option><option value="true">Yes</option>
                              </select></FG>
                              <FG label="Exercise Level"><select style={S.select} value={lifestyleForm.exercise} onChange={e=>setLifestyleForm(p=>({...p,exercise:e.target.value}))}>
                                {['sedentary','light','moderate','vigorous','athlete'].map(v=><option key={v} value={v}>{v.charAt(0).toUpperCase()+v.slice(1)}</option>)}
                              </select></FG>
                              <FG label="Exercise days/week"><input type="number" style={S.input} placeholder="0–7" min="0" max="7" value={lifestyleForm.exercise_days_per_week} onChange={e=>setLifestyleForm(p=>({...p,exercise_days_per_week:e.target.value}))} /></FG>
                              <FG label="Diet Type"><select style={S.select} value={lifestyleForm.diet} onChange={e=>setLifestyleForm(p=>({...p,diet:e.target.value}))}>
                                {['mixed','vegetarian','vegan','keto','diabetic','low-sodium','other'].map(v=><option key={v} value={v}>{v.charAt(0).toUpperCase()+v.slice(1)}</option>)}
                              </select></FG>
                              <FG label="Avg Sleep (hrs/night)"><input type="number" style={S.input} placeholder="e.g. 7" value={lifestyleForm.sleep_hours} onChange={e=>setLifestyleForm(p=>({...p,sleep_hours:e.target.value}))} /></FG>
                              <FG label="Occupation"><input style={S.input} placeholder="e.g. Software Engineer" value={lifestyleForm.occupation} onChange={e=>setLifestyleForm(p=>({...p,occupation:e.target.value}))} /></FG>
                              <FG label="Stress Level"><select style={S.select} value={lifestyleForm.stress_level} onChange={e=>setLifestyleForm(p=>({...p,stress_level:e.target.value}))}>
                                {['low','moderate','high','very high'].map(v=><option key={v} value={v}>{v.charAt(0).toUpperCase()+v.slice(1)}</option>)}
                              </select></FG>
                              <FG label="Recreational Drugs"><select style={S.select} value={lifestyleForm.recreational_drugs} onChange={e=>setLifestyleForm(p=>({...p,recreational_drugs:e.target.value==='true'}))}>
                                <option value="false">None</option><option value="true">Yes</option>
                              </select></FG>
                              <div style={{gridColumn:'span 2'}}><FG label="Additional Lifestyle Notes"><input style={S.input} placeholder="Diet restrictions, hobbies, or other relevant factors" value={lifestyleForm.notes} onChange={e=>setLifestyleForm(p=>({...p,notes:e.target.value}))} /></FG></div>
                              <div style={{gridColumn:'span 2',display:'flex',gap:'8px',justifyContent:'flex-end'}}>
                                <button type="button" style={S.cancelBtn} onClick={()=>setEditingLifestyle(false)}>Cancel</button>
                                <button type="submit" style={S.saveBtn}>Save Lifestyle</button>
                              </div>
                            </div>
                          </form>
                        </div>
                      ) : (
                        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(200px,1fr))', gap:'12px' }}>
                          {[
                            { icon:'🚬', label:'Smoking', value: lifestyle.smoking, note: lifestyle.smoking_packs_per_day?`${lifestyle.smoking_packs_per_day} packs/day`:'', warn: lifestyle.smoking==='current' },
                            { icon:'🍺', label:'Alcohol', value: lifestyle.alcohol, note: lifestyle.alcohol_units_per_week?`${lifestyle.alcohol_units_per_week} units/wk`:'', warn: lifestyle.alcohol==='heavy' },
                            { icon:'🏃', label:'Exercise', value: lifestyle.exercise, note: lifestyle.exercise_days_per_week?`${lifestyle.exercise_days_per_week}×/wk`:'' },
                            { icon:'🥗', label:'Diet', value: lifestyle.diet || '—' },
                            { icon:'😴', label:'Sleep', value: lifestyle.sleep_hours?`${lifestyle.sleep_hours} hrs/night`:'—' },
                            { icon:'💼', label:'Occupation', value: lifestyle.occupation || '—' },
                            { icon:'🧠', label:'Stress Level', value: lifestyle.stress_level, warn: lifestyle.stress_level==='high'||lifestyle.stress_level==='very high' },
                            { icon:'🌿', label:'Tobacco Chewing', value: lifestyle.tobacco_chewing?'Yes':'No', warn: lifestyle.tobacco_chewing },
                          ].map(v=>(
                            <div key={v.label} style={{...S.card,padding:'16px'}}>
                              <div style={{fontSize:'20px',marginBottom:'6px'}}>{v.icon}</div>
                              <div style={{fontSize:'14px',fontWeight:'700',color:v.warn?'#ef4444':'#0f172a',textTransform:'capitalize'}}>{v.value||'—'}</div>
                              {v.note&&<div style={{fontSize:'11px',color:'#94a3b8',marginTop:'2px'}}>{v.note}</div>}
                              <div style={{fontSize:'11px',color:'#94a3b8',marginTop:'3px'}}>{v.label}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                </div>
              </div>
            );
          }

          // ══════════════════════ PATIENT DASHBOARD (neumorphic) ══════════════════════
          const NS = {
            wrap:       { display:'flex', flexDirection:'column', gap:'24px', flex:1, minHeight:0, overflowY:'auto', paddingRight:'4px' },
            card:       { background:'linear-gradient(145deg,#FBFBFD,#ECECF1)', borderRadius:'22px', padding:'22px 24px', boxShadow:'8px 8px 18px rgba(209,209,214,.6), -8px -8px 18px rgba(255,255,255,.9)', border:'1px solid rgba(255,255,255,.6)' },
            statCard:   { background:'linear-gradient(145deg,#FBFBFD,#ECECF1)', borderRadius:'20px', padding:'16px 12px', boxShadow:'6px 6px 14px rgba(209,209,214,.55), -6px -6px 14px rgba(255,255,255,.9)', border:'1px solid rgba(255,255,255,.6)', textAlign:'center', display:'flex', flexDirection:'column', alignItems:'center', gap:'6px' },
            sectionTitle:{ fontSize:'13px', fontWeight:'800', color:'#1C1C1E', letterSpacing:'0.2px', margin:'0 0 14px', display:'flex', alignItems:'center', gap:'8px' },
            primaryBtn: { padding:'9px 18px', borderRadius:'50px', border:'none', cursor:'pointer', fontWeight:'700', fontSize:'12px', color:'#fff', background:'linear-gradient(135deg,#A88CFF,#7C5CFF)', boxShadow:'4px 4px 12px rgba(124,92,255,.35), -4px -4px 12px rgba(255,255,255,.9)' },
            ghostBtn:   { padding:'9px 18px', borderRadius:'50px', border:'1px solid #E2E8F0', background:'#F5F5F7', cursor:'pointer', fontSize:'12px', fontWeight:'700', color:'#6E6E73', boxShadow:'4px 4px 10px rgba(209,209,214,.5), -4px -4px 10px rgba(255,255,255,.9)' },
            link:       { fontSize:'12px', fontWeight:'700', color:'#7C5CFF', cursor:'pointer', background:'none', border:'none', display:'inline-flex', alignItems:'center', gap:'4px', padding:'0' },
            countPill:  { fontSize:'12px', fontWeight:'800', color:'#5B21B6', background:'#F0ECFF', padding:'2px 10px', borderRadius:'50px' },
          };
          const Ico = (name, size = 18, color = '#6C5CE7') => {
            const s = { width: size, height: size, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 };
            const icons = {
              heart: <svg style={s} viewBox="0 0 24 24" fill={color}><path d="M12 21s-7-4.5-8-10a4 4 0 0 1 7-2.7A4 4 0 0 1 20 11c-1 5.5-8 10-8 10z"/></svg>,
              pulse: <svg style={s} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>,
              pill: <svg style={s} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.5 1.5L13.5 4.5L4.5 13.5L1.5 10.5L10.5 1.5z"/><path d="M13.5 10.5L10.5 13.5L19.5 4.5L22.5 7.5L13.5 10.5z"/></svg>,
              alert: <svg style={s} viewBox="0 0 24 24" fill={color}><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/></svg>,
              calendar: <svg style={s} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>,
              doc: <svg style={s} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>,
              download: <svg style={s} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>,
              check: <svg style={s} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>,
              leaf: <svg style={s} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 20A7 7 0 0 1 9.8 6.6C15.5 4 20 10.5 20 17c0 2.5-1 5-3 7-1.5 1.5-3.5 2-5.5 1.5-1.5-.5-2.5-1.5-3-2.5-.5-1.5-1.5-2.5-2.5-3.5"/></svg>,
              thermometer: <svg style={s} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/></svg>,
              droplet: <svg style={s} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/></svg>,
              ruler: <svg style={s} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 3H3v18h18V3z"/><path d="M21 9H3M21 15H3M9 3v18M15 3v18" strokeWidth="1.5"/></svg>,
              calc: <svg style={s} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="8" y1="6" x2="16" y2="6"/><line x1="8" y1="10" x2="8" y2="10.01"/><line x1="12" y1="10" x2="12" y2="10.01"/><line x1="16" y1="10" x2="16" y2="10.01"/></svg>,
              edit: <svg style={s} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>,
            };
            return icons[name] || null;
          };
          const apptStatusStyle = (s) => {
            const st = String(s||'').toUpperCase();
            if (st==='CONFIRMED'||st==='SCHEDULED') return { bg:'#EDE9FE', color:'#5B21B6' };
            if (st==='PAYMENT_PENDING') return { bg:'#FFF7ED', color:'#c2410c' };
            if (st==='PENDING') return { bg:'#FEF3C7', color:'#D97706' };
            return { bg:'#EEEEF2', color:'#6E6E73' };
          };
          const fmtTime = (t) => { try { return new Date(t).toLocaleString('en-IN',{ day:'numeric', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' }); } catch { return '—'; } };

          const vitalsStats = [
            { icon:'droplet', label:'Blood Group', value: vitals.blood_group || '—' },
            { icon:'ruler', label:'Height / Weight', value: vitals.height && vitals.weight ? `${vitals.height} cm · ${vitals.weight} kg` : '—' },
            { icon:'calc', label:'BMI', value: vitals.bmi || (vitals.height&&vitals.weight ? bmiCalc(vitals.height,vitals.weight) : '—'), note: parseFloat(vitals.bmi||bmiCalc(vitals.height,vitals.weight))>=30?'Obese':parseFloat(vitals.bmi||bmiCalc(vitals.height,vitals.weight))>=25?'Overweight':parseFloat(vitals.bmi||bmiCalc(vitals.height,vitals.weight))>=18.5?'Normal':vitals.height?'Underweight':'' },
            { icon:'pulse', label:'Blood Pressure', value: vitals.blood_pressure || '—' },
            { icon:'heart', label:'Heart Rate', value: vitals.heart_rate ? `${vitals.heart_rate} bpm` : '—' },
            { icon:'droplet', label:'SpO₂', value: vitals.spo2 ? `${vitals.spo2}%` : '—' },
            { icon:'thermometer', label:'Temperature', value: vitals.temperature ? `${vitals.temperature}°F` : '—' },
            { icon:'droplet', label:'Sugar (F / PP)', value: [vitals.blood_sugar_fasting, vitals.blood_sugar_pp].filter(Boolean).join(' / ') || '—' },
          ];

          const upcomingAppts = appointments
            .filter(a => ['scheduled','confirmed'].includes(String(a.status||'').toLowerCase()))
            .sort((a,b)=> new Date(a.scheduled_time||a.appointmentDate||0) - new Date(b.scheduled_time||b.appointmentDate||0));

          const dashConditions = conditions.filter(c=>c.status==='active'||c.status==='chronic').slice(0,3);
          const dashMeds = medications.filter(m=>m.is_ongoing).slice(0,3);
          const dashAllergies = allergies.slice(0,3);

          const highlightCard = (icon, title, count, items, renderItem) => (
            <div style={NS.card}>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'12px' }}>
                <h3 style={{ ...NS.sectionTitle, margin:0 }}>{Ico(icon, 18)} {title}</h3>
                <span style={NS.countPill}>{count}</span>
              </div>
              {items.length === 0
                ? <p style={{ fontSize:'12px', color:'#6E6E73', margin:0 }}>Nothing recorded yet</p>
                : <div style={{ display:'flex', flexDirection:'column', gap:'8px' }}>
                    {items.map(renderItem)}
                  </div>}
            </div>
          );

          return (
            <div style={{ display:'flex', flexDirection:'column', flex:1, minHeight:0, paddingLeft:'32px', paddingRight:'32px' }}>
              {/* header */}
              <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'22px', flexShrink:0 }}>
                 <div>
                   <h2 style={{ margin:0, fontSize:'20px', color:'#1C1C1E', fontWeight:'800', letterSpacing:'-0.5px' }}>Medical History</h2>
                   <p style={{ margin:'4px 0 0', fontSize:'12px', color:'#6E6E73' }}>Your health at a glance</p>
                 </div>
              </div>

              <div style={NS.wrap}>
                {/* ── 1. Health Overview (vitals only) ── */}
                <div style={NS.card}>
                  <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'14px' }}>
                    <h3 style={NS.sectionTitle}><Ico name="heart" size={20} color="#ef4444" /> Health Overview</h3>
                  </div>
                  <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(150px,1fr))', gap:'14px' }}>
                    {vitalsStats.map(v=>(
                      <div key={v.label} style={NS.statCard}>
                        <div style={{ display:'flex', alignItems:'center', justifyContent:'center' }}>{Ico(v.icon, 22, '#1C1C1E')}</div>
                        <div style={{ fontSize:'16px', fontWeight:'800', color:'#1C1C1E' }}>{v.value}</div>
                        {v.note && <div style={{ fontSize:'10px', fontWeight:'700', color:'#7C5CFF' }}>{v.note}</div>}
                        <div style={{ fontSize:'11px', color:'#6E6E73' }}>{v.label}</div>
                       </div>
                         ))}
                     </div>
                   </div>

                {/* ── 2. Highlights of Medical History ── */}
                <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(240px,1fr))', gap:'16px' }}>
                  {highlightCard('pulse', 'Active Conditions', conditions.filter(c=>c.status==='active'||c.status==='chronic').length, dashConditions, c=>(
                    <div key={c.id} style={{ display:'flex', alignItems:'center', gap:'8px' }}>
                      <span style={{ width:'8px', height:'8px', borderRadius:'50%', background: statusColor[c.status]||'#7C5CFF', flexShrink:0 }}></span>
                      <span style={{ fontSize:'12px', fontWeight:'600', color:'#1C1C1E', flex:1 }}>{c.condition}</span>
                    </div>
                  ))}
                  {highlightCard('pill', 'Current Medications', medications.filter(m=>m.is_ongoing).length, dashMeds, m=>(
                    <div key={m.id} style={{ padding:'2px 0' }}>
                      <div style={{ fontSize:'12px', fontWeight:'700', color:'#1C1C1E' }}>{m.name}</div>
                      <div style={{ fontSize:'11px', color:'#6E6E73' }}>{m.dosage}{m.frequency?` · ${m.frequency}`:''}</div>
                    </div>
                  ))}
                  {highlightCard('alert', 'Allergies', allergies.length, dashAllergies, a=>(
                    <div key={a.id} style={{ display:'flex', alignItems:'center', gap:'8px' }}>
                      <span style={{ fontSize:'10px', fontWeight:'700', padding:'2px 8px', borderRadius:'50px', background: allergyColor[a.severity]||'#f97316', color:'#fff' }}>{a.severity}</span>
                      <span style={{ fontSize:'12px', fontWeight:'600', color:'#1C1C1E', flex:1 }}>{a.allergen}</span>
                      <span style={{ fontSize:'11px', color:'#6E6E73' }}>{a.reaction}</span>
                    </div>
                  ))}
                </div>

                {/* ── 3. Upcoming Appointments ── */}
                <div style={NS.card}>
                  <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'14px' }}>
                    <h3 style={NS.sectionTitle}><Ico name="calendar" size={18} color="#6C5CE7" /> Upcoming Appointments</h3>
                    <button style={NS.primaryBtn} onClick={()=>setActivePanelFromNav('appointments')}>+ Book New</button>
                  </div>
                  {upcomingAppts.length === 0 ? (
                    <div style={{ textAlign:'center', padding:'22px', background:'linear-gradient(145deg,#FBFBFD,#ECECF1)', borderRadius:'16px', border:'1px dashed #C4B5FD' }}>
                      <div style={{ fontSize:'30px', marginBottom:'8px', display:'flex', alignItems:'center', justifyContent:'center' }}><Ico name="calendar" size={32} color="#6C5CE7" /></div>
                      <div style={{ fontSize:'13px', fontWeight:'700', color:'#1C1C1E' }}>No upcoming appointments</div>
                      <div style={{ fontSize:'12px', color:'#6E6E73', margin:'4px 0 14px' }}>Book a slot with a doctor to get started.</div>
                      <button style={NS.primaryBtn} onClick={()=>setActivePanelFromNav('appointments')}>Book Appointment</button>
                    </div>
                  ) : (
                    <div style={{ display:'flex', flexDirection:'column', gap:'12px' }}>
                      {upcomingAppts.map((appt,i)=>(
                        <div key={i} style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'14px 16px', borderRadius:'16px', background:'linear-gradient(145deg,#FBFBFD,#ECECF1)', boxShadow:'5px 5px 12px rgba(209,209,214,.5), -5px -5px 12px rgba(255,255,255,.85)', border:'1px solid rgba(255,255,255,.6)' }}>
                          <div>
                            <div style={{ fontSize:'13px', fontWeight:'700', color:'#1C1C1E' }}>Dr. {appt.doctor_display || '—'}</div>
                            <div style={{ fontSize:'12px', color:'#6E6E73', marginTop:'3px' }}>{fmtTime(appt.scheduled_time || appt.appointmentDate)}</div>
                          </div>
                          <span style={{ fontSize:'11px', fontWeight:'700', padding:'5px 12px', borderRadius:'50px', background: apptStatusStyle(appt.status).bg, color: apptStatusStyle(appt.status).color }}>
                            {String(appt.status||'').toUpperCase()}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* ── 4. Latest Prescription (or Wellness fallback) ── */}
                {latestRx ? (
                  <div style={NS.card}>
                    <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'14px' }}>
                      <h3 style={NS.sectionTitle}><Ico name="pill" size={18} color="#6C5CE7" /> Latest Prescription</h3>
                      {latestRx.sickNote && <span style={{ fontSize:'11px', fontWeight:'700', padding:'4px 10px', borderRadius:'50px', background:'#FFF7ED', color:'#c2410c' }}><Ico name="doc" size={14} color="#c2410c" /> Sick Note</span>}
                    </div>
                    <div style={{ display:'flex', flexWrap:'wrap', gap:'10px 28px', marginBottom:'14px' }}>
                      <div><div style={{ fontSize:'10px', fontWeight:'700', color:'#6E6E73', textTransform:'uppercase', letterSpacing:'.5px' }}>Rx #</div><div style={{ fontSize:'13px', fontWeight:'700', color:'#1C1C1E' }}>{latestRx.prescriptionNumber}</div></div>
                      <div><div style={{ fontSize:'10px', fontWeight:'700', color:'#6E6E73', textTransform:'uppercase', letterSpacing:'.5px' }}>Doctor</div><div style={{ fontSize:'13px', fontWeight:'700', color:'#1C1C1E' }}>{latestRx.doctorName || '—'}</div></div>
                      <div><div style={{ fontSize:'10px', fontWeight:'700', color:'#6E6E73', textTransform:'uppercase', letterSpacing:'.5px' }}>Issued</div><div style={{ fontSize:'13px', fontWeight:'700', color:'#1C1C1E' }}>{fmtTime(latestRx.issuedAt)}</div></div>
                    </div>
                    <div style={{ display:'flex', flexDirection:'column', gap:'6px', marginBottom:'16px' }}>
                      {(latestRx.medicines||[]).slice(0,3).map((m,idx)=>(
                        <div key={idx} style={{ display:'flex', alignItems:'center', gap:'8px', fontSize:'12px', color:'#1C1C1E' }}>
                          <span style={{ width:'6px', height:'6px', borderRadius:'50%', background:'#7C5CFF', flexShrink:0 }}></span>
                          <span style={{ fontWeight:'600' }}>{m.name}</span>
                          <span style={{ color:'#6E6E73' }}>{m.dosage}{m.frequency?` · ${m.frequency}`:''}</span>
                        </div>
                      ))}
                      {(latestRx.medicines||[]).length === 0 && <div style={{ fontSize:'12px', color:'#6E6E73' }}>No medicines listed</div>}
                    </div>
                    <div style={{ display:'flex', gap:'10px', flexWrap:'wrap' }}>
                      <button style={NS.primaryBtn} onClick={()=>window.open(prescriptionApi.pdfUrl(latestRx.id), '_blank')}><Ico name="download" size={14} color="#fff" /> Download PDF</button>
                      {latestRx.qrToken && <button style={NS.ghostBtn} onClick={()=>navigate(`/verify/${latestRx.qrToken}`)}><Ico name="check" size={14} color="#fff" /> Verify</button>}
                    </div>
                  </div>
                ) : (
                  <div style={NS.card}>
                    <div style={{ display:'flex', alignItems:'center', gap:'14px' }}>
                      <div style={{ fontSize:'30px', display:'flex', alignItems:'center', justifyContent:'center' }}><Ico name="leaf" size={32} color="#16a34a" /></div>
                      <div style={{ flex:1 }}>
                        <h3 style={{ ...NS.sectionTitle, margin:'0 0 4px' }}>Wellness</h3>
                        <p style={{ margin:0, fontSize:'12px', color:'#6E6E73' }}>Stay on top of your health — book a check-up or ask our AI assistant a question.</p>
                        <div style={{ display:'flex', gap:'10px', marginTop:'12px', flexWrap:'wrap' }}>
                          <button style={NS.primaryBtn} onClick={()=>setActivePanelFromNav('appointments')}>Book Appointment</button>
                          <button style={NS.ghostBtn} onClick={()=>setActivePanelFromNav('explain')}>Ask AI Assistant</button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
}
