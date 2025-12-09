import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { authAPI } from '../services/api';
import './Auth.css';

function Profile() {
  const { user, updateProfile, changePassword, deleteAccount, refreshProfile, logout } = useAuth();
  const navigate = useNavigate();
  
  // Profile update state
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [profileError, setProfileError] = useState('');
  const [profileSuccess, setProfileSuccess] = useState('');
  const [profileLoading, setProfileLoading] = useState(false);
  
  // Password change state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [passwordSuccess, setPasswordSuccess] = useState('');
  const [passwordLoading, setPasswordLoading] = useState(false);
  
  // Delete account state
  const [deletePassword, setDeletePassword] = useState('');
  const [deleteError, setDeleteError] = useState('');
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  
  // Stats state
  const [stats, setStats] = useState(null);

  useEffect(() => {
    if (user) {
      setUsername(user.username);
      setEmail(user.email);
    }
  }, [user]);

  useEffect(() => {
    const loadStats = async () => {
      try {
        const response = await authAPI.getProfile();
        setStats(response.data.stats);
      } catch (error) {
        console.error('Failed to load stats:', error);
      }
    };
    loadStats();
  }, []);

  const handleProfileUpdate = async (e) => {
    e.preventDefault();
    setProfileError('');
    setProfileSuccess('');
    setProfileLoading(true);

    const result = await updateProfile(username, email);
    
    if (result.success) {
      setProfileSuccess('Profile updated successfully!');
      await refreshProfile();
    } else {
      setProfileError(result.error);
    }
    
    setProfileLoading(false);
  };

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    setPasswordError('');
    setPasswordSuccess('');

    if (newPassword !== confirmNewPassword) {
      setPasswordError('Passwords do not match');
      return;
    }

    if (newPassword.length < 8) {
      setPasswordError('Password must be at least 8 characters');
      return;
    }

    setPasswordLoading(true);
    const result = await changePassword(currentPassword, newPassword);
    
    if (result.success) {
      setPasswordSuccess('Password changed successfully!');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmNewPassword('');
    } else {
      setPasswordError(result.error);
    }
    
    setPasswordLoading(false);
  };

  const handleDeleteAccount = async (e) => {
    e.preventDefault();
    setDeleteError('');
    setDeleteLoading(true);

    const result = await deleteAccount(deletePassword);
    
    if (result.success) {
      navigate('/');
    } else {
      setDeleteError(result.error);
    }
    
    setDeleteLoading(false);
  };

  if (!user) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <h1>Please login to view your profile</h1>
          <button 
            onClick={() => navigate('/login')}
            className="auth-button"
          >
            Go to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container" style={{ paddingTop: '40px', paddingBottom: '40px', alignItems: 'flex-start' }}>
      <div className="auth-card" style={{ maxWidth: '600px' }}>
        <button 
          onClick={() => navigate('/')}
          style={{ 
            background: 'transparent', 
            border: 'none', 
            color: '#007acc', 
            cursor: 'pointer',
            marginBottom: '20px',
            fontSize: '14px'
          }}
        >
          ← Back to App
        </button>

        <h1>Profile Settings</h1>
        <p className="auth-subtitle">Manage your account settings</p>

        {/* Statistics */}
        {stats && (
          <div style={{ 
            background: '#1e1e1e', 
            padding: '20px', 
            borderRadius: '8px',
            marginBottom: '30px'
          }}>
            <h3 style={{ color: '#fff', marginTop: 0 }}>Your Progress</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
              <div>
                <div style={{ color: '#888', fontSize: '12px' }}>Problems Attempted</div>
                <div style={{ color: '#fff', fontSize: '24px', fontWeight: 'bold' }}>
                  {stats.total_attempted}
                </div>
              </div>
              <div>
                <div style={{ color: '#888', fontSize: '12px' }}>Problems Solved</div>
                <div style={{ color: '#007acc', fontSize: '24px', fontWeight: 'bold' }}>
                  {stats.total_completed}
                </div>
              </div>
              <div>
                <div style={{ color: '#888', fontSize: '12px' }}>Success Rate</div>
                <div style={{ color: '#fff', fontSize: '24px', fontWeight: 'bold' }}>
                  {stats.completion_rate.toFixed(1)}%
                </div>
              </div>
              <div>
                <div style={{ color: '#888', fontSize: '12px' }}>Total Messages</div>
                <div style={{ color: '#fff', fontSize: '24px', fontWeight: 'bold' }}>
                  {stats.total_messages}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Update Profile */}
        <div style={{ marginBottom: '30px' }}>
          <h2 style={{ color: '#fff', fontSize: '20px', marginBottom: '15px' }}>Update Profile</h2>
          
          {profileError && <div className="error-message">{profileError}</div>}
          {profileSuccess && <div className="error-message" style={{ background: '#22bb33' }}>{profileSuccess}</div>}
          
          <form onSubmit={handleProfileUpdate} className="auth-form">
            <div className="form-group">
              <label>Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={profileLoading}
                minLength={3}
                maxLength={30}
              />
            </div>
            
            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={profileLoading}
              />
            </div>
            
            <button type="submit" className="auth-button" disabled={profileLoading}>
              {profileLoading ? 'Updating...' : 'Update Profile'}
            </button>
          </form>
        </div>

        {/* Change Password */}
        <div style={{ marginBottom: '30px' }}>
          <h2 style={{ color: '#fff', fontSize: '20px', marginBottom: '15px' }}>Change Password</h2>
          
          {passwordError && <div className="error-message">{passwordError}</div>}
          {passwordSuccess && <div className="error-message" style={{ background: '#22bb33' }}>{passwordSuccess}</div>}
          
          <form onSubmit={handlePasswordChange} className="auth-form">
            <div className="form-group">
              <label>Current Password</label>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                disabled={passwordLoading}
                required
              />
            </div>
            
            <div className="form-group">
              <label>New Password</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                disabled={passwordLoading}
                required
                minLength={8}
              />
            </div>
            
            <div className="form-group">
              <label>Confirm New Password</label>
              <input
                type="password"
                value={confirmNewPassword}
                onChange={(e) => setConfirmNewPassword(e.target.value)}
                disabled={passwordLoading}
                required
              />
            </div>
            
            <button type="submit" className="auth-button" disabled={passwordLoading}>
              {passwordLoading ? 'Changing...' : 'Change Password'}
            </button>
          </form>
        </div>

        {/* Delete Account */}
        <div>
          <h2 style={{ color: '#ff4444', fontSize: '20px', marginBottom: '15px' }}>Danger Zone</h2>
          
          {!showDeleteConfirm ? (
            <button 
              onClick={() => setShowDeleteConfirm(true)}
              className="auth-button"
              style={{ background: '#ff4444' }}
            >
              Delete Account
            </button>
          ) : (
            <>
              {deleteError && <div className="error-message">{deleteError}</div>}
              
              <form onSubmit={handleDeleteAccount} className="auth-form">
                <p style={{ color: '#ff4444', marginBottom: '15px' }}>
                  ⚠️ This action cannot be undone. All your data will be permanently deleted.
                </p>
                
                <div className="form-group">
                  <label>Confirm with your password</label>
                  <input
                    type="password"
                    value={deletePassword}
                    onChange={(e) => setDeletePassword(e.target.value)}
                    placeholder="Enter your password"
                    disabled={deleteLoading}
                    required
                  />
                </div>
                
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button 
                    type="button"
                    onClick={() => {
                      setShowDeleteConfirm(false);
                      setDeletePassword('');
                      setDeleteError('');
                    }}
                    className="auth-button"
                    style={{ flex: 1, background: '#666' }}
                  >
                    Cancel
                  </button>
                  <button 
                    type="submit"
                    className="auth-button"
                    style={{ flex: 1, background: '#ff4444' }}
                    disabled={deleteLoading}
                  >
                    {deleteLoading ? 'Deleting...' : 'Confirm Delete'}
                  </button>
                </div>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default Profile;
