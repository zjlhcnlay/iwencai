/**
 * 同花顺问财 hexin-v / cookie(v) 加解密
 *
 * 算法来源: https://s.thsi.cn/js/chameleon/chameleon.1.9.min.js
 * - 自定义 Base64 字母表 (URL-safe)
 * - XOR 流压缩 + 校验和
 * - 18 字段指纹包
 *
 * hexin-v 请求头与 cookie 中的 v 值相同。
 */

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';

/** 各字段序列化宽度（字节数） */
const WIDTHS = [4, 4, 4, 4, 1, 1, 1, 3, 2, 2, 2, 2, 2, 2, 2, 4, 2, 1];

const FIELD_NAMES = [
  'random',
  'serverTime',
  'clientTime',
  'uaHash',
  'osType',
  'browserType',
  'pluginNum',
  'clickCount',
  'scrollCount',
  'reserved9',
  'mouseX',
  'mouseY',
  'reserved12',
  'reserved13',
  'reserved14',
  'sessionCounter',
  'updateCounter',
  'versionFlag',
];

function b64decode(str) {
  const map = Object.create(null);
  for (let i = 0; i < 64; i++) map[ALPHABET[i]] = i;
  const out = [];
  let buf = 0;
  let bits = 0;
  for (const ch of str) {
    if (map[ch] === undefined) continue;
    buf = (buf << 6) | map[ch];
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      out.push((buf >> bits) & 255);
      buf &= (1 << bits) - 1;
    }
  }
  return out;
}

function b64encode(bytes) {
  let out = '';
  for (let i = 0; i < bytes.length; i += 3) {
    const a = bytes[i];
    const b = bytes[i + 1] ?? 0;
    const c = bytes[i + 2] ?? 0;
    const tri = (a << 16) | (b << 8) | c;
    out += ALPHABET[(tri >> 18) & 63] + ALPHABET[(tri >> 12) & 63];
    if (i + 1 < bytes.length) out += ALPHABET[(tri >> 6) & 63];
    if (i + 2 < bytes.length) out += ALPHABET[tri & 63];
  }
  return out;
}

/** djb 风格校验和，取低 8 位 */
function checksum(bytes) {
  let u = 0;
  for (const n of bytes) u = (((u << 5) - u + n) >>> 0);
  return u & 255;
}

function compressXor(raw, cs) {
  const out = [3, cs];
  let c = cs;
  for (const b of raw) {
    out.push(b ^ (c & 255));
    c = (~(131 * c)) >>> 0;
  }
  return out;
}

function decompressXor(bytes, start, cs) {
  const out = [];
  let c = cs;
  for (let r = start; r < bytes.length; r++) {
    out.push(bytes[r] ^ (c & 255));
    c = (~(131 * c)) >>> 0;
  }
  return out;
}

function pack(fields) {
  const raw = [];
  for (let i = 0; i < WIDTHS.length; i++) {
    let f = (fields[i] ?? 0) >>> 0;
    const w = WIDTHS[i];
    for (let k = w - 1; k >= 0; k--) raw.push((f >> (8 * k)) & 255);
  }
  return raw;
}

function unpack(raw) {
  let e = 0;
  const fields = [];
  for (const w of WIDTHS) {
    let f = 0;
    for (let k = 0; k < w; k++) f = (f << 8) | (raw[e++] || 0);
    fields.push(f >>> 0);
  }
  return fields;
}

/**
 * 解密 hexin-v / cookie v
 * @param {string} token
 * @returns {{ checksum: number, fields: number[], meta: Record<string, number> }}
 */
function decodeHexinV(token) {
  const bytes = b64decode(token);
  if (bytes[0] !== 3) throw new Error(`invalid prefix: ${bytes[0]}`);
  const cs = bytes[1];
  const raw = decompressXor(bytes, 2, cs);
  if (checksum(raw) !== cs) throw new Error('checksum mismatch');
  const fields = unpack(raw);
  const meta = Object.fromEntries(fields.map((v, i) => [FIELD_NAMES[i], v]));
  return { checksum: cs, fields, meta };
}

/**
 * 加密生成 hexin-v
 * @param {number[]} fields 18 个 uint32 字段
 */
function encodeHexinV(fields) {
  if (fields.length !== WIDTHS.length) {
    throw new Error(`expected ${WIDTHS.length} fields, got ${fields.length}`);
  }
  const raw = pack(fields);
  const cs = checksum(raw);
  return b64encode(compressXor(raw, cs));
}

/**
 * 构造问财 Web 端指纹字段（简化版，可过大部分接口）
 * @param {object} opts
 * @param {number} [opts.serverTime] TOKEN_SERVER_TIME（秒）
 * @param {number} [opts.clientTime] 客户端时间（秒）
 * @param {string} [opts.userAgent]
 */
function buildFingerprint(opts = {}) {
  const serverTime = opts.serverTime ?? Math.floor(Date.now() / 1000);
  const clientTime = opts.clientTime ?? Math.floor(Date.now() / 1000);
  const ua = opts.userAgent ?? 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36';

  let uaHash = 0;
  for (let i = 0; i < ua.length; i++) {
    uaHash = (((uaHash << 5) - uaHash + ua.charCodeAt(i)) >>> 0);
  }

  return [
    (Math.random() * 0xffffffff) >>> 0,
    serverTime,
    clientTime,
    uaHash >>> 0,
    1,
    10,
    5,
    opts.clickCount ?? 0,
    opts.scrollCount ?? 0,
    0,
    opts.mouseX ?? 0,
    opts.mouseY ?? 0,
    0,
    opts.reserved14 ?? 0,
    0,
    opts.sessionCounter ?? 0,
    opts.updateCounter ?? 0,
    3,
  ];
}

module.exports = {
  ALPHABET,
  WIDTHS,
  FIELD_NAMES,
  decodeHexinV,
  encodeHexinV,
  buildFingerprint,
};

if (require.main === module) {
  const token = process.argv[2];
  if (!token) {
    console.log('用法: node hexin-v.js <hexin-v-token>');
    process.exit(1);
  }
  console.log(JSON.stringify(decodeHexinV(token), null, 2));
}
