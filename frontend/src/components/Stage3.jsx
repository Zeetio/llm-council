import { memo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './Stage3.css';

/**
 * 画像カード: クリックで拡大、エラー時は非表示
 */
function ImageCard({ image }) {
  const [failed, setFailed] = useState(false);
  const [expanded, setExpanded] = useState(false);

  if (failed) return null;

  return (
    <>
      <div className="related-image" onClick={() => setExpanded(true)}>
        <img
          src={image.url}
          alt={image.description || '関連画像'}
          loading="lazy"
          onError={() => setFailed(true)}
        />
        {image.description && (
          <div className="related-image__caption">{image.description}</div>
        )}
      </div>

      {/* ライトボックス（拡大表示） */}
      {expanded && (
        <div className="lightbox" onClick={() => setExpanded(false)}>
          <div className="lightbox__content" onClick={(e) => e.stopPropagation()}>
            <button className="lightbox__close" onClick={() => setExpanded(false)}>
              ×
            </button>
            <img
              src={image.url}
              alt={image.description || '関連画像'}
            />
            {image.description && (
              <p className="lightbox__caption">{image.description}</p>
            )}
          </div>
        </div>
      )}
    </>
  );
}

// メモ化してpropsが変わらない限り再レンダーしない
export default memo(function Stage3({ finalResponse }) {
  if (!finalResponse) {
    return null;
  }

  const images = finalResponse.images || [];

  return (
    <div className="stage stage3">
      <h3 className="stage-title">Stage 3: Final Council Answer</h3>
      <div className="final-response">
        <div className="chairman-label">
          Chairman: {finalResponse.model.split('/')[1] || finalResponse.model}
        </div>
        <div className="final-text markdown-content">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {finalResponse.response}
          </ReactMarkdown>
        </div>

        {/* 関連画像 */}
        {images.length > 0 && (
          <div className="related-images">
            <div className="related-images__header">
              <span className="related-images__icon">🖼️</span>
              <span className="related-images__title">関連画像</span>
            </div>
            <div className="related-images__grid">
              {images.map((img, i) => (
                <ImageCard key={i} image={img} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
});
