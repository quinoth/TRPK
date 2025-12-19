// src/components/DocumentFlow.tsx
import React, { useState, useEffect, useCallback } from 'react';

interface DocumentFile {
  id: string;
  name: string;
  size: string;
  status: 'draft' | 'signed';
  createdAt: string;
}

// Форматирование размера файла
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Б';
  const k = 1024;
  const sizes = ['Б', 'КБ', 'МБ'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// Конфигурация
const DOCFLOW_SERVICE_URL = 'http://localhost:8002';

// Компонент строки файла
const FileRow = React.memo(({ file, onDownload, onSign, onDelete }: {
  file: DocumentFile;
  onDownload: () => void;
  onSign: () => void;
  onDelete: () => void;
}) => (
  <tr key={file.id} className="border-b hover:bg-gray-50 transition-colors duration-150">
    <td className="px-6 py-3 font-medium truncate max-w-xs" title={file.name}>
      {file.name}
    </td>
    <td className="px-6 py-3 text-gray-600">{file.size}</td>
    <td className="px-6 py-3 text-gray-600">{file.createdAt}</td>
    <td className="px-6 py-3">
      <span
        className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
          file.status === 'signed'
            ? 'bg-green-100 text-green-800'
            : 'bg-yellow-100 text-yellow-800'
        }`}
      >
        {file.status === 'signed' ? 'Подписан' : 'Черновик'}
      </span>
    </td>
    <td className="px-6 py-3 space-x-1.5 flex flex-wrap gap-y-1">
      <button
        onClick={onDownload}
        className="px-2.5 py-1 bg-gray-600 text-white text-xs rounded hover:bg-gray-700 min-w-[68px]"
        aria-label="Скачать файл"
      >
        Скачать
      </button>
      {file.status !== 'signed' && (
        <button
          onClick={onSign}
          className="px-2.5 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 min-w-[68px]"
          aria-label="Подписать файл"
        >
          Подписать
        </button>
      )}
      <button
        onClick={onDelete}
        className="px-2.5 py-1 bg-red-600 text-white text-xs rounded hover:bg-red-700 min-w-[68px]"
        aria-label="Удалить файл"
      >
        Удалить
      </button>
    </td>
  </tr>
));
FileRow.displayName = 'FileRow';

// Компонент строки корзины
const TrashRow = React.memo(({ file, onRestore, onPermanentDelete }: {
  file: DocumentFile;
  onRestore: () => void;
  onPermanentDelete: () => void;
}) => (
  <tr key={file.id} className="border-b hover:bg-gray-50 transition-colors duration-150">
    <td className="px-6 py-3 font-medium truncate max-w-xs" title={file.name}>
      {file.name}
    </td>
    <td className="px-6 py-3 text-gray-600">{file.size}</td>
    <td className="px-6 py-3 text-gray-600">{file.createdAt}</td>
    <td className="px-6 py-3 text-gray-500">—</td>
    <td className="px-6 py-3 space-x-1.5 flex flex-wrap gap-y-1">
      <button
        onClick={onRestore}
        className="px-2.5 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700 min-w-[76px]"
        aria-label="Восстановить файл"
      >
        Восстановить
      </button>
      <button
        onClick={onPermanentDelete}
        className="px-2.5 py-1 bg-red-600 text-white text-xs rounded hover:bg-red-700 min-w-[90px]"
        aria-label="Удалить навсегда"
      >
        Удалить навсегда
      </button>
    </td>
  </tr>
));
TrashRow.displayName = 'TrashRow';

const DocumentFlow: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [searchLoading, setSearchLoading] = useState(false); // отдельно для поиска
  const [error, setError] = useState('');
  const [files, setFiles] = useState<DocumentFile[]>([]);
  const [trash, setTrash] = useState<DocumentFile[]>([]);
  const [activeTab, setActiveTab] = useState<'files' | 'trash'>('files');
  const [searchQuery, setSearchQuery] = useState('');
  const [uploading, setUploading] = useState(false);

  const token = localStorage.getItem('auth_token');

  console.log(' Токен авторизации:', token ? 'есть' : 'отсутствует');

  // --- Загрузка активных файлов ---
  const loadFiles = async (query = '') => {
    try {
      if (!query) setSearchLoading(true);
      setLoading(!query); // полная загрузка только при первом входе или смене вкладки

      const url = new URL(`${DOCFLOW_SERVICE_URL}/api/docs/search`);
      if (query) url.searchParams.append('q', query);

      console.log('➡️ Запрос:', url.toString());

      const res = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      console.log('⬅️ Ответ:', res.status);

      if (!res.ok) {
        const text = await res.text();
        console.error(' Ошибка ответа:', text);
        throw new Error(`Ошибка загрузки файлов: ${res.status}`);
      }

      const data = await res.json();
      console.log(' Полученные данные:', data);

      const docs = Array.isArray(data.results) ? data.results : [];

      const mapped = docs
        .filter((d: any) => d.deleted_at === null || d.deleted_at === undefined)
        .map((d: any) => ({
          id: String(d.id),
          name: d.title || 'Без названия',
          size: formatFileSize(d.file_size),
          status: d.is_signed ? 'signed' : 'draft',
          createdAt: new Date(d.created_at).toLocaleString(),
        }));

      setFiles(mapped);
      setError('');
    } catch (err: any) {
      console.error(' Ошибка при загрузке файлов:', err);
      setError(err.message || 'Не удалось загрузить файлы');
    } finally {
      setLoading(false);
      setSearchLoading(false);
    }
  };

  // --- Загрузка корзины ---
  const loadTrash = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${DOCFLOW_SERVICE_URL}/api/docs/trash`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      console.log('⬅️ Ответ корзины:', res.status);

      if (!res.ok) {
        const text = await res.text();
        console.error(' Ошибка корзины:', text);
        throw new Error(`Ошибка загрузки корзины: ${res.status}`);
      }

      const data = await res.json();
      console.log(' Корзина:', data);

      const docs = Array.isArray(data.trash) ? data.trash : [];

      const mapped = docs.map((d: any) => ({
        id: String(d.id),
        name: d.title || 'Удалённый файл',
        size: formatFileSize(d.file_size || 0),
        status: 'draft',
        createdAt: new Date(d.deleted_at).toLocaleString(),
      }));

      setTrash(mapped);
      setError('');
    } catch (err: any) {
      console.error(' Ошибка при загрузке корзины:', err);
      setError(err.message || 'Не удалось загрузить корзину');
    } finally {
      setLoading(false);
    }
  };

  // --- Поиск с дебаунсом ---
  useEffect(() => {
    const handler = setTimeout(() => {
      if (activeTab === 'files') {
        loadFiles(searchQuery);
      }
    }, 300);

    return () => clearTimeout(handler);
  }, [searchQuery, activeTab]);

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value;
    console.log('🔎 Ввод в поиск:', query);
    setSearchQuery(query);
  };

  // --- Подписание ---
  const handleSign = useCallback(async (fileId: string) => {
    if (!window.confirm('Подписать этот файл?')) return;

    try {
      console.log('✍️ Подписываем файл:', fileId);
      const res = await fetch(`${DOCFLOW_SERVICE_URL}/api/docs/sign/${fileId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!res.ok) throw new Error('Не удалось подписать');

      console.log(' Файл подписан');
      loadFiles(searchQuery);
    } catch (err: any) {
      console.error(' Ошибка подписи:', err);
      setError(`Ошибка подписи: ${err.message}`);
    }
  }, [token, searchQuery]);

  // --- Скачивание ---
  const handleDownload = useCallback(async (fileId: string, fileName: string) => {
    try {
      console.log('⬇️ Скачиваем:', fileName, '(ID:', fileId, ')');
      const res = await fetch(`${DOCFLOW_SERVICE_URL}/api/docs/download/${fileId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!res.ok) throw new Error('Файл не найден или нет доступа');

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      console.log(' Скачано:', fileName);
    } catch (err: any) {
      console.error(' Ошибка скачивания:', err);
      setError(`Ошибка скачивания: ${err.message}`);
    }
  }, [token]);

  // --- Загрузка нового файла ---
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileInput = e.target;
    if (!fileInput.files || fileInput.files.length === 0) return;

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    try {
      console.log('📤 Загружаем файл:', file.name, file.size, 'bytes');
      setUploading(true);

      const res = await fetch(`${DOCFLOW_SERVICE_URL}/api/docs/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });

      if (!res.ok) {
        const text = await res.text();
        console.error(' Ошибка загрузки:', text);
        throw new Error('Не удалось загрузить файл');
      }

      console.log(' Файл загружен');
      fileInput.value = '';
      loadFiles(searchQuery);
    } catch (err: any) {
      console.error(' Ошибка при загрузке:', err);
      setError(`Ошибка загрузки: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  // --- Мягкое удаление ---
  const handleDelete = useCallback(async (fileId: string) => {
    if (!window.confirm('Переместить файл в корзину?')) return;

    try {
      console.log('🗑 Помещаем в корзину:', fileId);
      const res = await fetch(`${DOCFLOW_SERVICE_URL}/api/docs/${fileId}?confirm=true`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!res.ok) throw new Error('Не удалось удалить');

      console.log(' Файл в корзине');
      loadFiles(searchQuery);
    } catch (err: any) {
      console.error(' Ошибка удаления:', err);
      setError(`Ошибка удаления: ${err.message}`);
    }
  }, [token, searchQuery]);

  // --- Восстановление из корзины ---
  const handleRestore = useCallback(async (fileId: string) => {
    if (!window.confirm('Восстановить файл из корзины?')) return;

    try {
      console.log('🔄 Восстанавливаем из корзины:', fileId);
      const res = await fetch(`${DOCFLOW_SERVICE_URL}/api/docs/restore/${fileId}?confirm=true`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!res.ok) throw new Error('Не удалось восстановить');

      console.log(' Файл восстановлен');
      loadTrash();
      loadFiles();
    } catch (err: any) {
      console.error(' Ошибка восстановления:', err);
      setError(`Ошибка восстановления: ${err.message}`);
    }
  }, [token]);

  // --- Окончательное удаление ---
  const handlePermanentDelete = useCallback(async (fileId: string) => {
    if (!window.confirm('Удалить файл навсегда? Это действие нельзя отменить.')) return;

    try {
      console.log('💀 Удаляем навсегда:', fileId);
      const res = await fetch(`${DOCFLOW_SERVICE_URL}/api/docs/trash/${fileId}?confirm=true`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!res.ok) throw new Error('Не удалось удалить навсегда');

      console.log(' Файл удалён навсегда');
      setTrash(prev => prev.filter(f => f.id !== fileId));
    } catch (err: any) {
      console.error(' Ошибка окончательного удаления:', err);
      setError(`Ошибка окончательного удаления: ${err.message}`);
    }
  }, [token]);

  // --- Загрузка данных при монтировании и смене вкладки ---
  useEffect(() => {
    if (activeTab === 'files') {
      loadFiles(searchQuery);
    } else {
      loadTrash();
    }
  }, [activeTab]); // searchQuery обрабатывается через debounce внутри loadFiles

  // Показываем общий лоадер только при первой загрузке или смене вкладки
  if (loading && !searchLoading) {
    return (
      <div className="flex justify-center items-center h-40">
        <div className="text-lg text-gray-600">Загрузка...</div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Управление файлами</h1>

      {error && (
        <div className="mb-4 p-3 bg-red-100 border border-red-300 text-red-700 rounded text-sm whitespace-pre-wrap font-mono text-xs">
          {error}
        </div>
      )}

      {/* Вкладки */}
      <div className="flex gap-1 mb-6 border-b">
        {[
          { key: 'files', label: 'Файлы' },
          { key: 'trash', label: 'Корзина' }
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as any)}
            className={`px-6 py-3 font-semibold capitalize transition ${
              activeTab === tab.key
                ? 'border-b-3 border-blue-600 text-blue-700'
                : 'text-gray-600 hover:text-gray-800'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Поиск и загрузка */}
      {activeTab === 'files' && (
        <div className="mb-6 space-y-4">
          <div className="relative">
            <input
              type="text"
              placeholder="Поиск по названию..."
              value={searchQuery}
              onChange={handleSearch}
              className="w-full px-4 py-2 pl-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition-shadow duration-200"
              aria-label="Поиск файлов"
            />
            {searchLoading && (
              <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
                <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
              </div>
            )}
          </div>
          <label className="block">
            <span className="sr-only">Загрузить файл</span>
            <input
              type="file"
              onChange={handleUpload}
              disabled={uploading}
              className="block w-full text-sm text-gray-500
                file:mr-4 file:py-2 file:px-4
                file:rounded-full file:border-0
                file:text-sm file:font-semibold
                file:bg-blue-50 file:text-blue-700
                hover:file:bg-blue-100"
            />
          </label>
          {uploading && <p className="text-sm text-gray-500">Загрузка файла...</p>}
        </div>
      )}

      {/* Индикатор поиска */}
      {searchLoading && (
        <div className="mb-4 text-sm text-gray-500 italic">Поиск файл... {searchQuery}</div>
      )}

      {/* Таблица */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full table-auto">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Имя файла</th>
              <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Размер</th>
              <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Дата</th>
              <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Статус</th>
              <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Действия</th>
            </tr>
          </thead>
          <tbody>
            {(activeTab === 'files' ? files : trash).length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-10 text-center text-gray-500">
                  {activeTab === 'files'
                    ? searchQuery
                      ? 'Файлы по запросу не найдены'
                      : 'Файлы не найдены'
                    : 'Корзина пуста'}
                </td>
              </tr>
            ) : activeTab === 'files' ? (
              files.map(file => (
                <FileRow
                  key={file.id}
                  file={file}
                  onDownload={() => handleDownload(file.id, file.name)}
                  onSign={() => handleSign(file.id)}
                  onDelete={() => handleDelete(file.id)}
                />
              ))
            ) : (
              trash.map(file => (
                <TrashRow
                  key={file.id}
                  file={file}
                  onRestore={() => handleRestore(file.id)}
                  onPermanentDelete={() => handlePermanentDelete(file.id)}
                />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default DocumentFlow;