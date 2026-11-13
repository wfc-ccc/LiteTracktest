-- ============================================================================
-- LiteTrack 自动化测试 · 测试账号与项目造数脚本
--
--   目标库 ：litetrack（与 config/env.yaml 里 db.database 保持一致）
--   明文口令：123456
--   口令密文：BCrypt，$2a$，strength=10（与后端 spring-security-crypto 一致）
--   幂等性 ：可重复执行，已存在的账号走 ON DUPLICATE KEY UPDATE
--
--   执行方式：Navicat 打开查询窗口整段执行，或
--             mysql -uroot -p123456 litetrack < sql/seed_test_accounts.sql
-- ============================================================================

SET NAMES utf8mb4;

-- ---------------------------------------------------------------------------
-- 1. 四个角色账号
--    表 sys_user：username 唯一键，role ∈ ADMIN / PM / DEV / QA
--    status=1 启用，is_deleted=0 未删除
--    四个账号共用同一段密文，明文都是 123456
-- ---------------------------------------------------------------------------
INSERT INTO sys_user (username, password, real_name, role, status, is_deleted, create_time)
VALUES
  ('admin', '$2a$10$9goDoReo4Jxt6P4JttQh/uHwIGiBAlFQjOXFrnwrhtNiks8YzB.zO', '系统管理员', 'ADMIN', 1, 0, NOW()),
  ('pm01',  '$2a$10$9goDoReo4Jxt6P4JttQh/uHwIGiBAlFQjOXFrnwrhtNiks8YzB.zO', '项目经理',   'PM',    1, 0, NOW()),
  ('dev01', '$2a$10$9goDoReo4Jxt6P4JttQh/uHwIGiBAlFQjOXFrnwrhtNiks8YzB.zO', '开发一号',   'DEV',   1, 0, NOW()),
  ('qa01',  '$2a$10$9goDoReo4Jxt6P4JttQh/uHwIGiBAlFQjOXFrnwrhtNiks8YzB.zO', '测试一号',   'QA',    1, 0, NOW())
ON DUPLICATE KEY UPDATE
  password   = VALUES(password),
  real_name  = VALUES(real_name),
  role       = VALUES(role),
  status     = 1,
  is_deleted = 0;

-- ---------------------------------------------------------------------------
-- 2. 造数项目（owner 指向 pm01，便于 PM 直接可见）
--    conftest 的 project_id 夹具会用 PM 身份取「可见的第一个项目」
-- ---------------------------------------------------------------------------
INSERT INTO project (name, description, owner_id, status, create_time, update_time)
SELECT '轻舟自动化验收项目', '自动化测试造数用，勿删', u.id, 'ACTIVE', NOW(), NOW()
FROM sys_user u
WHERE u.username = 'pm01'
  AND NOT EXISTS (SELECT 1 FROM project p WHERE p.name = '轻舟自动化验收项目');

-- ---------------------------------------------------------------------------
-- 3. 项目成员：PM / DEV / QA 都加进来
--    新建任务弹窗的「指派给」下拉只列项目内的 DEV / QA，没有成员就选不到人
-- ---------------------------------------------------------------------------
INSERT INTO project_member (project_id, user_id)
SELECT p.id, u.id
FROM project p
JOIN sys_user u ON u.username IN ('pm01', 'dev01', 'qa01')
WHERE p.name = '轻舟自动化验收项目'
  AND NOT EXISTS (
    SELECT 1 FROM project_member m
    WHERE m.project_id = p.id AND m.user_id = u.id
  );

-- ---------------------------------------------------------------------------
-- 4. 自检：应看到 4 个账号与 1 个项目
-- ---------------------------------------------------------------------------
SELECT id, username, real_name, role, status FROM sys_user ORDER BY id;

SELECT p.id AS project_id, p.name, p.status, u.username AS owner
FROM project p
JOIN sys_user u ON u.id = p.owner_id
WHERE p.name = '轻舟自动化验收项目';
