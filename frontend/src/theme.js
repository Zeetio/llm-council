/**
 * テーマ管理モジュール
 * ライト/ダーク/自動モードを管理し、localStorageに永続化
 */

const THEME_KEY = 'theme_mode';

/**
 * 現在のテーマ設定を取得
 * @returns {'light' | 'dark' | 'auto'} テーマモード
 */
export function getTheme() {
  return localStorage.getItem(THEME_KEY) || 'auto';
}

/**
 * テーマを設定し、DOMに適用
 * @param {'light' | 'dark' | 'auto'} mode テーマモード
 */
export function setTheme(mode) {
  localStorage.setItem(THEME_KEY, mode);
  applyTheme(mode);
}

/**
 * テーマをDOMに適用
 * @param {'light' | 'dark' | 'auto'} mode テーマモード
 */
export function applyTheme(mode) {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = mode === 'auto' ? (prefersDark ? 'dark' : 'light') : mode;
  document.documentElement.setAttribute('data-theme', theme);
}

/**
 * テーマシステムを初期化
 * - 保存されたテーマを適用
 * - システム設定変更を監視
 */
export function initTheme() {
  applyTheme(getTheme());

  // システム設定変更を監視（自動モード時に反映）
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (getTheme() === 'auto') {
      applyTheme('auto');
    }
  });
}
