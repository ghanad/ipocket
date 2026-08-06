export type UserRole = "Viewer" | "Editor" | "Admin";

export interface UserPolicy {
  can_edit_role: boolean;
  can_deactivate: boolean;
  can_delete: boolean;
  delete_disabled_reason: string | null;
}

export interface UserRow {
  id: number;
  username: string;
  role: UserRole;
  role_label: "Viewer" | "Editor" | "Superuser";
  is_active: boolean;
  policy: UserPolicy;
}

export interface CurrentActor {
  id: number;
  username: string;
  role: UserRole;
}

export interface UsersResponse {
  actor: CurrentActor;
  users: UserRow[];
}

export interface CreateUserValues {
  username: string;
  password: string;
  can_edit: boolean;
  is_active: boolean;
}

export interface EditUserValues {
  password: string;
  can_edit: boolean;
  is_active: boolean;
}

export interface UserUpdateResponse {
  user: UserRow;
  changed: boolean;
}

export interface UsersBootstrap {
  mode: "create" | "edit" | "delete";
  errors: string[];
  form: Record<string, string>;
}
