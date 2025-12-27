import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import './Auth.css';

function UserProfile() {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = () => {
    logout();
    setMenuOpen(false);
    navigate('/login');
  };

  const handleProfile = () => {
    setMenuOpen(false);
    navigate('/profile');
  };

  if (!isAuthenticated) {
    return (
      <div style={{ display: 'flex', gap: '10px' }}>
        <button 
          onClick={() => navigate('/login')}
          className="user-profile-btn"
          style={{ padding: '6px 16px' }}
        >
          Sign In
        </button>
        <button 
          onClick={() => navigate('/register')}
          className="user-profile-btn"
          style={{ padding: '6px 16px', background: '#007acc' }}
        >
          Sign Up
        </button>
      </div>
    );
  }

  return (
    <div style={{ position: 'relative' }} ref={menuRef}>
      <button 
        className="user-profile-btn"
        onClick={() => setMenuOpen(!menuOpen)}
      >
        <span>👤</span>
        <span>{user?.username}</span>
        <span style={{ fontSize: '10px' }}>▼</span>
      </button>

      {menuOpen && (
        <div className="user-profile-menu">
          <div className="user-profile-menu-item" onClick={handleProfile}>
            View Profile
          </div>
          <div className="user-profile-menu-item logout" onClick={handleLogout}>
            Logout
          </div>
        </div>
      )}
    </div>
  );
}

export default UserProfile;
