/**
 * auth-ui.js - 用户认证UI组件
 * 提供登录/注册模态框和用户状态显示
 */
(() => {
  'use strict';
  
  let currentUser = null;
  let authModal = null;
  
  /**
   * 创建认证模态框
   */
  function createAuthModal() {
    if (authModal) return authModal;
    
    const modal = document.createElement('div');
    modal.className = 'maint-auth-modal';
    modal.innerHTML = `
      <div class="maint-auth-modal__overlay" data-auth-close></div>
      <div class="maint-auth-modal__panel">
        <button class="maint-auth-modal__close" data-auth-close type="button">&times;</button>
        <div class="maint-auth-modal__tabs">
          <button class="maint-auth-modal__tab is-active" data-auth-tab="login">登录</button>
          <button class="maint-auth-modal__tab" data-auth-tab="register">注册</button>
        </div>
        <form class="maint-auth-modal__form" data-auth-form="login">
          <div class="maint-auth-field">
            <label for="auth-email">邮箱</label>
            <input type="email" id="auth-email" name="email" required autocomplete="email">
          </div>
          <div class="maint-auth-field">
            <label for="auth-password">密码</label>
            <input type="password" id="auth-password" name="password" required autocomplete="current-password">
          </div>
          <div class="maint-auth-error" data-auth-error hidden></div>
          <button type="submit" class="maint-auth-submit">登录</button>
        </form>
        <form class="maint-auth-modal__form" data-auth-form="register" hidden>
          <div class="maint-auth-field">
            <label for="reg-email">邮箱</label>
            <input type="email" id="reg-email" name="email" required autocomplete="email">
          </div>
          <div class="maint-auth-field">
            <label for="reg-username">用户名</label>
            <input type="text" id="reg-username" name="username" required autocomplete="username">
          </div>
          <div class="maint-auth-field">
            <label for="reg-password">密码</label>
            <input type="password" id="reg-password" name="password" required autocomplete="new-password">
          </div>
          <div class="maint-auth-error" data-auth-error hidden></div>
          <button type="submit" class="maint-auth-submit">注册</button>
        </form>
      </div>
    `;
    
    document.body.appendChild(modal);
    authModal = modal;
    
    // 绑定事件
    modal.querySelectorAll('[data-auth-close]').forEach(el => {
      el.addEventListener('click', closeAuthModal);
    });
    
    modal.querySelectorAll('[data-auth-tab]').forEach(tab => {
      tab.addEventListener('click', () => switchAuthTab(tab.dataset.authTab));
    });
    
    modal.querySelector('[data-auth-form="login"]').addEventListener('submit', handleLogin);
    modal.querySelector('[data-auth-form="register"]').addEventListener('submit', handleRegister);
    
    return modal;
  }
  
  /**
   * 打开认证模态框
   */
  function openAuthModal(tab = 'login') {
    createAuthModal();
    switchAuthTab(tab);
    authModal.hidden = false;
    document.body.style.overflow = 'hidden';
  }
  
  /**
   * 关闭认证模态框
   */
  function closeAuthModal() {
    if (authModal) {
      authModal.hidden = true;
      document.body.style.overflow = '';
      clearAuthErrors();
    }
  }
  
  /**
   * 切换登录/注册标签
   */
  function switchAuthTab(tab) {
    const tabs = authModal.querySelectorAll('[data-auth-tab]');
    const forms = authModal.querySelectorAll('[data-auth-form]');
    
    tabs.forEach(t => t.classList.toggle('is-active', t.dataset.authTab === tab));
    forms.forEach(f => f.hidden = f.dataset.authForm !== tab);
    
    clearAuthErrors();
  }
  
  /**
   * 显示错误信息
   */
  function showAuthError(formType, message) {
    const form = authModal.querySelector(`[data-auth-form="${formType}"]`);
    const errorEl = form.querySelector('[data-auth-error]');
    errorEl.textContent = message;
    errorEl.hidden = false;
  }
  
  /**
   * 清除错误信息
   */
  function clearAuthErrors() {
    authModal.querySelectorAll('[data-auth-error]').forEach(el => {
      el.hidden = true;
      el.textContent = '';
    });
  }
  
  /**
   * 处理登录
   */
  async function handleLogin(e) {
    e.preventDefault();
    clearAuthErrors();
    
    const form = e.target;
    const email = form.email.value;
    const password = form.password.value;
    
    try {
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || '登录失败');
      }
      
      // 保存令牌
      localStorage.setItem('wanyu.access_token', data.access_token);
      localStorage.setItem('wanyu.refresh_token', data.refresh_token);
      
      currentUser = data.user;
      onAuthSuccess();
      closeAuthModal();
      
    } catch (error) {
      showAuthError('login', error.message);
    }
  }
  
  /**
   * 处理注册
   */
  async function handleRegister(e) {
    e.preventDefault();
    clearAuthErrors();
    
    const form = e.target;
    const email = form.email.value;
    const username = form.username.value;
    const password = form.password.value;
    
    try {
      const response = await fetch('/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, username, password })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || '注册失败');
      }
      
      // 保存令牌
      localStorage.setItem('wanyu.access_token', data.access_token);
      localStorage.setItem('wanyu.refresh_token', data.refresh_token);
      
      currentUser = data.user;
      onAuthSuccess();
      closeAuthModal();
      
    } catch (error) {
      showAuthError('register', error.message);
    }
  }
  
  /**
   * 认证成功回调
   */
  function onAuthSuccess() {
    updateUserUI();
    
    // 触发自定义事件
    document.dispatchEvent(new CustomEvent('wanyu:auth-changed', {
      detail: { user: currentUser }
    }));
  }
  
  /**
   * 更新用户UI显示
   */
  function updateUserUI() {
    const userMenu = document.querySelector('#maint-user-menu');
    if (!userMenu) return;
    
    if (currentUser) {
      userMenu.innerHTML = `
        <button class="maint-user-button" type="button" data-user-toggle>
          <span class="maint-user-avatar">${(currentUser.display_name || currentUser.username)[0]}</span>
          <span class="maint-user-name">${escapeHtml(currentUser.display_name || currentUser.username)}</span>
        </button>
        <div class="maint-user-dropdown" data-user-dropdown hidden>
          <a href="#saved" data-maintain-view="saved">我的收藏</a>
          ${currentUser.is_admin ? '<a href="#admin" data-maintain-view="admin">管理后台</a>' : ''}
          <button type="button" data-auth-logout>退出登录</button>
        </div>
      `;
      
      // 绑定事件
      userMenu.querySelector('[data-user-toggle]').addEventListener('click', () => {
        const dropdown = userMenu.querySelector('[data-user-dropdown]');
        dropdown.hidden = !dropdown.hidden;
      });
      
      userMenu.querySelector('[data-auth-logout]')?.addEventListener('click', logout);
      
      // 点击外部关闭下拉菜单
      document.addEventListener('click', (e) => {
        if (!userMenu.contains(e.target)) {
          userMenu.querySelector('[data-user-dropdown]').hidden = true;
        }
      });
    } else {
      userMenu.innerHTML = `
        <button class="maint-auth-button" type="button" data-auth-login>登录</button>
      `;
      userMenu.querySelector('[data-auth-login]').addEventListener('click', () => openAuthModal('login'));
    }
  }
  
  /**
   * 退出登录
   */
  function logout() {
    localStorage.removeItem('wanyu.access_token');
    localStorage.removeItem('wanyu.refresh_token');
    currentUser = null;
    updateUserUI();
    
    document.dispatchEvent(new CustomEvent('wanyu:auth-changed', {
      detail: { user: null }
    }));
  }
  
  /**
   * 检查登录状态
   */
  async function checkAuthStatus() {
    const token = localStorage.getItem('wanyu.access_token');
    if (!token) return;
    
    try {
      const response = await fetch('/api/v1/auth/me', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        currentUser = await response.json();
        updateUserUI();
        
        // 同步用户数据
        document.dispatchEvent(new CustomEvent('wanyu:auth-changed', {
          detail: { user: currentUser }
        }));
      } else {
        // 令牌无效，清除
        localStorage.removeItem('wanyu.access_token');
        localStorage.removeItem('wanyu.refresh_token');
      }
    } catch (e) {
      console.warn('[AuthUI] 检查登录状态失败:', e);
    }
  }
  
  /**
   * 获取当前用户
   */
  function getCurrentUser() {
    return currentUser;
  }
  
  /**
   * 获取访问令牌
   */
  function getAccessToken() {
    return localStorage.getItem('wanyu.access_token');
  }
  
  /**
   * HTML转义
   */
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
  
  /**
   * 初始化认证UI
   */
  function initAuthUI() {
    // 创建用户菜单容器
    const header = document.querySelector('.maint-header__tools');
    if (header && !document.querySelector('#maint-user-menu')) {
      const userMenu = document.createElement('div');
      userMenu.id = 'maint-user-menu';
      userMenu.className = 'maint-user-menu';
      header.appendChild(userMenu);
    }
    
    updateUserUI();
    checkAuthStatus();
  }
  
  // 导出
  const authApi = {
    initAuthUI,
    openAuthModal,
    closeAuthModal,
    logout,
    getCurrentUser,
    getAccessToken
  };
  
  if (typeof window !== 'undefined') {
    window.WanyuAuth = authApi;
  }
})();
