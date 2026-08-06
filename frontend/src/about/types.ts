export interface AboutData {
  application: {
    name: string;
  };
  build: {
    version: string;
    commit: string;
    build_time: string;
  };
  links: {
    health: string;
    metrics: string;
  };
}
