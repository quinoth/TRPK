import React, { useState, useEffect, useRef } from 'react';

// === Типы ===
interface User {
  id: number;
  email: string;
  full_name?: string;
}

interface Group {
  id: number;
  name: string;
  is_direct: boolean;
  member_count: number;
  created_by_id: number;
  last_updated: string;
  is_archived: boolean;
}

interface FormattedMessage {
  id: string;
  userId: number;
  userName: string;
  userAvatar: string;
  text: string;
  timestamp: string;
  isOwn: boolean;
}

// === Конфиг API ===
const CHAT_API_BASE = 'http://127.0.0.1:8005/api/chat';
const CHAT_WS_URL = 'ws://127.0.0.1:8005/api/chat/ws';

// === Универсальный fetch с логами ===
const debugFetch = async (url: string, options: RequestInit): Promise<Response> => {
  console.group(` [API] ${options.method || 'GET'} → ${url}`);
  console.log('📝 Headers:', options.headers);
  if (options.body) console.log('📤 Body:', options.body);

  try {
    const response = await fetch(url, options);
    console.log(' Status:', response.status);

    const contentType = response.headers.get('content-type');
    let data = null;
    if (contentType && contentType.includes('application/json')) {
      const text = await response.clone().text();
      try {
        data = JSON.parse(text);
        console.log(' JSON:', data);
      } catch (e) {
        console.log(' Raw:', text);
      }
    }

    if (!response.ok) {
      const errorText = await response.text();
      console.error(' Error:', errorText);
      throw new Error(data?.detail || errorText || 'Network error');
    }

    console.groupEnd();
    return response;
  } catch (err: any) {
    console.error(' Fetch failed:', err.message);
    console.groupEnd();
    throw err;
  }
};

// === API клиент ===
const chatAPI = {
  getUsers: async (): Promise<User[]> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('Требуется авторизация (нет токена)');

    const res = await debugFetch(`${CHAT_API_BASE}/users`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
    return await res.json();
  },

  getGroups: async (): Promise<Group[]> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('Требуется авторизация (нет токена)');

    const res = await debugFetch(`${CHAT_API_BASE}/groups`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
    return await res.json();
  },

  createChat: async (memberIds: number[], name?: string): Promise<number> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('Требуется авторизация');

    const res = await debugFetch(`${CHAT_API_BASE}/create-chat`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ member_ids: memberIds, name })
    });

    const data = await res.json();
    return data.group_id;
  },

  sendGroupMessage: async (groupId: number, content: string): Promise<void> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('Требуется авторизация');

    const res = await debugFetch(`${CHAT_API_BASE}/group/${groupId}/message`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ content: content.trim() })
    });
    await res.json();
  },

  getGroupHistory: async (groupId: number): Promise<FormattedMessage[]> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('Требуется авторизация');

    const res = await debugFetch(`${CHAT_API_BASE}/history/group/${groupId}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    const data = await res.json();
    const myId = Number(localStorage.getItem('userId'));

    return data.messages.map((msg: any) => ({
      id: msg.sent_at,
      userId: msg.from,
      userName: msg.from_name || msg.from_email,
      userAvatar: `/avatars/${msg.from_email}.jpg`,
      text: msg.content,
      timestamp: new Date(msg.sent_at).toLocaleTimeString(),
      isOwn: msg.from === myId
    }));
  },

  archiveGroup: async (groupId: number): Promise<void> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('Требуется авторизация');

    const res = await debugFetch(`${CHAT_API_BASE}/group/${groupId}/archive`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
    await res.json();
  },

  unarchiveGroup: async (groupId: number): Promise<void> => {
    const token = localStorage.getItem('auth_token');
    if (!token) throw new Error('Требуется авторизация');

    const res = await debugFetch(`${CHAT_API_BASE}/group/${groupId}/unarchive`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
    await res.json();
  }
};

// === Компонент ===
const PsychologistChat: React.FC = () => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [messages, setMessages] = useState<FormattedMessage[]>([]);
  const [messageInput, setMessageInput] = useState<string>('');

  const [users, setUsers] = useState<User[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);

  const [selectedChat, setSelectedChat] = useState<{
    type: 'group';
    target: number;
    name: string;
  } | null>(null);

  // Поиск
  const [searchTerm, setSearchTerm] = useState<string>('');

  // Создание группы
  const [isCreatingGroup, setIsCreatingGroup] = useState<boolean>(false);
  const [newGroupName, setNewGroupName] = useState<string>('');
  const [selectedMembers, setSelectedMembers] = useState<Set<number>>(new Set());

  // Подменю действий с чатом
  const [showGroupActions, setShowGroupActions] = useState<number | null>(null);

  // --- Получение userId и прав ---
  const rawUserId = localStorage.getItem('userId');
  const currentUserId = rawUserId ? parseInt(rawUserId, 10) : null;

  const currentUserEmail = localStorage.getItem('userEmail') || 'me@example.com';
  const currentUserName = localStorage.getItem('userName') || currentUserEmail.split('@')[0];

  // Проверка прав: services.admin.write
  const rawUserAttrs = localStorage.getItem('userAttributes');
  let isAdminWrite = false;
  try {
    const attrs = JSON.parse(rawUserAttrs || '{}');
    isAdminWrite = !!attrs?.services?.admin?.write;
  } catch (e) {
    console.warn('Failed to parse user attributes:', e);
  }

  // --- Проверка авторизации и загрузка данных ---
  useEffect(() => {
    console.log('🧩 [App Init]', { rawUserId, currentUserId, currentUserEmail });

    if (currentUserId === null || isNaN(currentUserId)) {
      setError('Ошибка: некорректный userId');
      setLoading(false);
      return;
    }

    if (!localStorage.getItem('auth_token')) {
      setError('Ошибка: отсутствует auth_token');
      setLoading(false);
      return;
    }

    const loadInitialData = async () => {
      try {
        setLoading(true);
        const [loadedUsers, loadedGroups] = await Promise.all([
          chatAPI.getUsers(),
          chatAPI.getGroups()
        ]);
        setUsers(loadedUsers);
        setGroups(loadedGroups);
        console.log(' Загружено пользователей:', loadedUsers.length);
        console.log(' Загружено групп:', loadedGroups.length);
      } catch (err: any) {
        setError(`Ошибка загрузки: ${err.message}`);
      } finally {
        setLoading(false);
      }
    };

    loadInitialData();
  }, [currentUserId]);

  // --- Загрузка истории чата ---
  useEffect(() => {
    if (!selectedChat || !currentUserId) return;

    const loadHistory = async () => {
      try {
        setLoading(true);
        const history = await chatAPI.getGroupHistory(selectedChat.target);
        setMessages(history);
      } catch (err: any) {
        setError(`История недоступна: ${err.message}`);
      } finally {
        setLoading(false);
      }
    };

    loadHistory();
  }, [selectedChat, currentUserId]);

  // --- WebSocket подключение ---
  useEffect(() => {
    if (!currentUserId) return;

    const token = localStorage.getItem('auth_token');
    if (!token) return;

    const wsUrl = `${CHAT_WS_URL}?token=${encodeURIComponent(token)}`;
    console.log('🔗 Подключение WebSocket:', wsUrl);

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log(' WebSocket подключён');
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        console.log(' WS:', data);

        if (data.type === 'message' && selectedChat?.target === data.group_id) {
          setMessages(prev => [...prev, {
            id: data.sent_at,
            userId: data.from,
            userName: data.from_name || data.from_email,
            userAvatar: `/avatars/${data.from_email}.jpg`,
            text: data.content,
            timestamp: new Date(data.sent_at).toLocaleTimeString(),
            isOwn: data.from === currentUserId
          }]);
        }
      } catch (err) {
        console.error(' Ошибка парсинга WS:', err);
      }
    };

    ws.onerror = (err) => console.error(' WebSocket ошибка:', err);
    ws.onclose = () => console.log(' WebSocket закрыт');

    wsRef.current = ws;

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [currentUserId]);

  // --- Прокрутка к последнему сообщению ---
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // --- Отправка сообщения ---
  const sendMessage = () => {
    if (!messageInput.trim() || !selectedChat || !currentUserId) return;

    const trimmed = messageInput.trim();

    const localMsg: FormattedMessage = {
      id: Date.now().toString(),
      userId: currentUserId,
      userName: currentUserName,
      userAvatar: '/avatars/me.jpg',
      text: trimmed,
      timestamp: new Date().toLocaleTimeString(),
      isOwn: true
    };

    setMessages(prev => [...prev, localMsg]);
    setMessageInput('');

    chatAPI.sendGroupMessage(selectedChat.target, trimmed)
      .then(() => console.log('📤 Сообщение отправлено'))
      .catch(err => {
        setError(`Ошибка отправки: ${err.message}`);
        setMessages(prev => prev.filter(m => m.id !== localMsg.id));
      });
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // --- Фильтрация пользователей ---
  const filteredUsers = users.filter(u =>
    u.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (u.full_name || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  // --- Открыть диалог ---
  const openDirectChat = async (user: User) => {
    if (user.id === currentUserId) return;

    setLoading(true);
    try {
      const memberIds = [currentUserId, user.id];
      const name = user.full_name || user.email;

      const existing = groups.find(g =>
        g.is_direct &&
        g.member_count === 2 &&
        (g.created_by_id === currentUserId || g.created_by_id === user.id)
      );

      if (existing) {
        setSelectedChat({
          type: 'group',
          target: existing.id,
          name: existing.name
        });
      } else {
        const groupId = await chatAPI.createChat(memberIds, name);
        const newGroup: Group = {
          id: groupId,
          name,
          is_direct: true,
          member_count: 2,
          created_by_id: currentUserId,
          last_updated: new Date().toISOString(),
          is_archived: false
        };
        setGroups(prev => {
          if (prev.some(g => g.id === newGroup.id)) return prev;
          return [...prev, newGroup];
        });
        setSelectedChat({
          type: 'group',
          target: groupId,
          name
        });
      }
    } catch (err: any) {
      setError(`Не удалось создать диалог: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // --- Создание группы ---
  const startCreateGroup = () => {
    setIsCreatingGroup(true);
    setNewGroupName('');
    setSelectedMembers(new Set([currentUserId]));
  };

  const finishCreateGroup = async () => {
    const ids = Array.from(selectedMembers).filter(id => id > 0);
    if (ids.length < 2) {
      alert('Группа должна быть минимум из 2 человек');
      return;
    }

    const name = newGroupName.trim() || 'Новая группа';

    try {
      const groupId = await chatAPI.createChat(ids, name);
      const newGroup: Group = {
        id: groupId,
        name,
        is_direct: false,
        member_count: ids.length,
        created_by_id: currentUserId,
        last_updated: new Date().toISOString(),
        is_archived: false
      };
      setGroups(prev => {
        if (prev.some(g => g.id === newGroup.id)) return prev;
        return [...prev, newGroup];
      });
      setSelectedChat({
        type: 'group',
        target: groupId,
        name
      });
      setIsCreatingGroup(false);
      setNewGroupName('');
      setSelectedMembers(new Set());
    } catch (err: any) {
      setError(`Не удалось создать группу: ${err.message}`);
    }
  };

  const cancelCreateGroup = () => {
    setIsCreatingGroup(false);
    setNewGroupName('');
    setSelectedMembers(new Set());
  };

  const toggleMember = (id: number) => {
    setSelectedMembers(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (loading && !messages.length) {
    return <div className="p-8 text-center">Загрузка...</div>;
  }

  return (
    <div className="flex h-screen bg-white font-sans">
      {/* Сайдбар */}
      <div className="w-80 border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <h2 className="font-bold text-lg text-gray-900">Чаты</h2>
        </div>

        {/* Поиск и кнопки */}
        <div className="p-3 border-b space-y-2">
          <input
            type="text"
            placeholder="Поиск по email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none"
          />
          <button
            onClick={startCreateGroup}
            className="w-full text-sm bg-green-600 text-white py-1 rounded hover:bg-green-700"
          >
            + Создать группу
          </button>
        </div>

        {/* Модальное окно создания */}
        {isCreatingGroup && (
          <div className="p-3 bg-blue-50 border-b space-y-3">
            <input
              type="text"
              placeholder="Название группы"
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded text-sm"
              autoFocus
            />

            <div>
              <p className="text-xs text-gray-600 mb-1">Участники:</p>
              <div className="max-h-40 overflow-y-auto space-y-1">
                {filteredUsers.map(u => (
                  <label key={u.id} className="flex items-center gap-2 text-sm hover:bg-gray-100 p-1 rounded cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedMembers.has(u.id)}
                      onChange={() => toggleMember(u.id)}
                    />
                    {u.full_name || u.email}
                  </label>
                ))}
              </div>
            </div>

            <div className="flex gap-2">
              <button onClick={finishCreateGroup} className="flex-1 bg-blue-600 text-white text-xs py-1 rounded">
                Создать
              </button>
              <button onClick={cancelCreateGroup} className="flex-1 bg-gray-400 text-white text-xs py-1 rounded">
                Отмена
              </button>
            </div>
          </div>
        )}

        {/* Список пользователей и чатов */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-600 mb-2">Пользователи</h3>
            {filteredUsers.length === 0 ? (
              <p className="text-xs text-gray-500">Нет совпадений</p>
            ) : (
              filteredUsers
                .filter(u => u.id !== currentUserId)
                .map(u => (
                  <div
                    key={u.id}
                    onClick={() => openDirectChat(u)}
                    className="p-2 rounded cursor-pointer hover:bg-gray-100"
                  >
                    <p className="font-medium">{u.full_name || u.email}</p>
                    <p className="text-xs text-gray-500">Диалог</p>
                  </div>
                ))
            )}
          </div>

          {/* Мои чаты */}
          {groups.length > 0 && (
            <div className="border-t pt-2">
              <h3 className="text-sm font-semibold text-gray-600 mb-2">Мои чаты</h3>
              {groups.map(g => (
                <div key={g.id} className="relative">
                  <div
                    onClick={() => setSelectedChat({
                      type: 'group',
                      target: g.id,
                      name: g.name
                    })}
                    className={`p-2 rounded cursor-pointer ${
                      selectedChat?.target === g.id ? 'bg-blue-100' : 'hover:bg-gray-100'
                    } ${g.is_archived ? 'opacity-60 italic' : ''}`}
                  >
                    <p className="text-sm font-medium">{g.name}</p>
                    <p className="text-xs text-gray-500">
                      {g.member_count} участников
                      {g.is_archived && " • архивирован"}
                    </p>
                  </div>

                  {selectedChat?.target === g.id && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowGroupActions(prev => prev === g.id ? null : g.id);
                      }}
                      className="absolute right-2 top-2 text-xs bg-gray-200 hover:bg-gray-300 px-2 py-1 rounded"
                    >
                      •••
                    </button>
                  )}

                  {showGroupActions === g.id && (
                    <div className="absolute right-2 top-8 bg-white border rounded shadow-md z-10 w-48 p-2 text-sm">
                      {!g.is_archived ? (
                        g.created_by_id === currentUserId ? (
                          <button
                            onClick={async () => {
                              try {
                                await chatAPI.archiveGroup(g.id);
                                setGroups(prev => prev.map(gr => gr.id === g.id ? { ...gr, is_archived: true } : gr));
                                setShowGroupActions(null);
                              } catch (err: any) {
                                setError(`Ошибка архивации: ${err.message}`);
                              }
                            }}
                            className="block w-full text-left px-2 py-1 hover:bg-red-50 text-red-700"
                          >
                             Архивировать чат
                          </button>
                        ) : (
                          <p className="px-2 py-1 text-gray-500 text-center">
                            Только создатель может архивировать
                          </p>
                        )
                      ) : (
                        (isAdminWrite || g.created_by_id === currentUserId) ? (
                          <button
                            onClick={async () => {
                              try {
                                await chatAPI.unarchiveGroup(g.id);
                                setGroups(prev => prev.map(gr => gr.id === g.id ? { ...gr, is_archived: false } : gr));
                                setShowGroupActions(null);
                              } catch (err: any) {
                                setError(`Ошибка разархивации: ${err.message}`);
                              }
                            }}
                            className="block w-full text-left px-2 py-1 hover:bg-green-50 text-green-700"
                          >
                             Разархивировать чат
                          </button>
                        ) : (
                          <p className="px-2 py-1 text-gray-500 text-center">
                            Только создатель или администратор
                          </p>
                        )
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Чат */}
      <div className="flex-1 flex flex-col">
        {!selectedChat ? (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            Выберите пользователя или чат
          </div>
        ) : (
          <>
            {error && (
              <div className="p-2 bg-red-100 text-red-700 text-sm text-center" onClick={() => setError('')}>
                {error}
              </div>
            )}

            <div className="p-3 border-b bg-gray-50">
              <h3 className="font-semibold">{selectedChat.name}</h3>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
              {messages.map(msg => (
                <div key={msg.id} className={`flex ${msg.isOwn ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-xs px-4 py-2 rounded-lg shadow-sm ${
                      msg.isOwn ? 'bg-blue-600 text-white' : 'bg-white text-gray-800 shadow'
                    }`}
                  >
                    {!msg.isOwn && (
                      <p className="text-xs font-semibold text-gray-600 mb-1">{msg.userName}</p>
                    )}
                    <p className="text-sm">{msg.text}</p>
                    <p className="text-xs mt-1 opacity-70">{msg.timestamp}</p>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            <div className="p-4 border-t bg-white">
              {selectedChat && groups.find(g => g.id === selectedChat.target)?.is_archived ? (
                <div className="text-center text-gray-500 text-sm">
                  Чат архивирован. Сообщения отправлять нельзя.
                </div>
              ) : (
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={messageInput}
                    onChange={(e) => setMessageInput(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Введите сообщение..."
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none"
                  />
                  <button
                    onClick={sendMessage}
                    disabled={!messageInput.trim()}
                    className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    Отправить
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default PsychologistChat;