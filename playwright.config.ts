import { defineConfig } from "@playwright/test";
const database=process.env.TEST_DATABASE_URL;
if(!database || !new URL(database).pathname.endsWith("_test"))throw new Error("Set TEST_DATABASE_URL to a disposable database ending in _test.");
export default defineConfig({
 testDir:"./tests/e2e",fullyParallel:false,workers:1,timeout:60000,
 use:{baseURL:"http://127.0.0.1:3100",trace:"retain-on-failure",screenshot:"only-on-failure"},
 projects:[{name:"mobile",use:{browserName:"chromium",viewport:{width:375,height:812},isMobile:true,hasTouch:true}},{name:"desktop",use:{browserName:"chromium",viewport:{width:1440,height:1000}}}],
 webServer:{command:"pnpm build && pnpm start --hostname 127.0.0.1 --port 3100",url:"http://127.0.0.1:3100",timeout:180000,reuseExistingServer:false,env:{DATABASE_URL:database,APP_URL:"http://127.0.0.1:3100",NEXT_TELEMETRY_DISABLED:"1"}}
});
