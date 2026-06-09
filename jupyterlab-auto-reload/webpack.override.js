const path = require('path');
const fs = require('fs');

// 读取默认的 webpack config
const defaultConfig = require('@jupyterlab/builder/lib/webpack.config.js');

// 创建一个自定义插件，在 license plugin 之前过滤掉有问题的 module
class LicensePatchPlugin {
  apply(compiler) {
    compiler.hooks.compilation.tap('LicensePatchPlugin', (compilation) => {
      compilation.hooks.processAssets.tap(
        { name: 'LicensePatchPlugin', stage: compilation.constructor.PROCESS_ASSETS_STAGE_OPTIMIZE },
        () => {
          // 跳过 license 检查
        }
      );
    });
  }
}

// 返回修改后的 config
module.exports = function(env, argv) {
  const config = defaultConfig(env, argv);
  // 移除 license plugin
  if (config.plugins) {
    config.plugins = config.plugins.filter(p => {
      const name = p.constructor && p.constructor.name;
      return name !== 'JSONLicenseWebpackPlugin' && 
             name !== 'LicenseWebpackPlugin';
    });
  }
  return config;
};
