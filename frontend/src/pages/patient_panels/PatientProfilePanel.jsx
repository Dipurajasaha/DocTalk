import React from 'react';

export default function PatientProfilePanel({
  user,
  handleProfileUpdate,
  isUploadingProfile
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, paddingLeft: '32px', paddingRight: '32px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', justifyContent: 'center' }}>
          <h2 style={{ margin: 0, fontSize: '18px', color: '#6C5CE7', fontWeight: 'bold', textAlign: 'left', width: '100%', fontFamily: '"Poppins", system-ui, -apple-system, sans-serif', letterSpacing: '-0.5px' }}>Edit Profile</h2>
        </div>
      </div>
      
      <div className="profile-edit-container neu-convex" style={{ display: 'flex', flexDirection: 'column', borderRadius: '16px', padding: '32px', overflowY: 'auto', maxWidth: '500px', width: '100%', boxSizing: 'border-box' }}>
        <form onSubmit={handleProfileUpdate} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '12px', fontWeight: '600', color: '#64748B' }}>Display Name</label>
            <input type="text" name="display_name" defaultValue={user?.name || user?.display_name || ''} className="neu-input" style={{ fontSize: '14px' }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '12px', fontWeight: '600', color: '#64748B' }}>Profile Picture</label>
            <input type="file" name="profile_pic" accept="image/*" className="neu-input" style={{ fontSize: '14px' }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '12px', fontWeight: '600', color: '#64748B' }}>New Password (leave blank to keep current)</label>
            <input type="password" name="password" placeholder="Enter new password..." className="neu-input" style={{ fontSize: '14px' }} />
          </div>
          <button type="submit" disabled={isUploadingProfile} className="neu-btn-accent" style={{ marginTop: '12px', padding: '14px', fontWeight: 'bold', cursor: 'pointer', fontSize: '14px', transition: 'all 0.3s', opacity: isUploadingProfile ? 0.7 : 1 }}>
            {isUploadingProfile ? 'Saving...' : 'Save Profile Changes'}
          </button>
        </form>
      </div>
    </div>
  );
}
