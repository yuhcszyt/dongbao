export type FamilyRole = 'owner' | 'admin' | 'member'
export interface FamilyOverview {
  id: string
  name: string
  role: FamilyRole
  user_id: string
  display_name: string
  members: { user_id: string; name: string; role: FamilyRole }[]
  families: { id: string; name: string; role: FamilyRole }[]
  invites: { id: string; expires_at: string }[]
}
export const roleName = (role: FamilyRole) => ({ owner: '创建者', admin: '管理员', member: '家人' })[role]
export const canRemoveMember = (actor: FamilyRole, target: FamilyRole) => target !== 'owner' && (actor === 'owner' || (actor === 'admin' && target === 'member'))
export interface FamilyAudit { id: string; action: string; actor_id: string | null; target_id: string | null; created_at: string }
export const auditName = (action: string) => ({ rename: '修改家庭名称', invite_created: '创建邀请', invite_revoked: '撤销邀请', member_joined: '加入家庭', member_left: '退出家庭', member_removed: '移除成员', role_changed: '修改角色', owner_transferred: '转交家庭管理', account_deleted: '成员注销账号' })[action] || '家庭设置更新'
