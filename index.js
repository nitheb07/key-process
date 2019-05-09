var exec = require('child_process').exec;
var express = require('express');
var app = express();
var fs = require('fs');
var temp = require('temp');
var mkdirp = require('mkdirp');
var path = require('path');

var tempCheckDir = path.join(__dirname,  '/temp/check/');
var tempOutputDir = path.join(__dirname,  '/temp/output/');

mkdirp(tempCheckDir, function(err){
  if (err) {
    console.error(err);
    throw err;
  }
  else {
    console.log('Created dir ' + tempCheckDir);
  }
});
mkdirp(tempOutputDir, function(err){
  if (err) {
    console.error(err);
    throw err;
  }
  else {
    console.log('Created dir ' + tempOutputDir);
  }
});

var callPython = function(req, res, tempPathParams, pythonFile, responseFunction) {
  var tempFile = temp.path(tempPathParams);
  console.log(tempFile);
  var data = new Buffer('');
  req.on('data', function(chunk) {
      data = Buffer.concat([data, chunk]);
  });
  req.on('end', function() {
    fs.writeFile(tempFile, data, (err) => {
      if(err){
        res.status(401).send('error writing to file ' + err);
        return;
      }
      var command = 'python ' + path.join(__dirname, '/python_scripts', pythonFile) + ' ' + tempFile + ' ' + tempOutputDir;
      console.log(command);
      exec(command, (execErr, stdout, stderr) => {
        if (execErr) {
          console.error(`exec error: ${execErr}`);
          console.log(`stdout: ` + stdout);
          console.log(`stderr: ` + stderr);
          res.status(401).send({ error: 'error parsing file' });
          return;
        }
        responseFunction(stdout, stderr, res);
      });
    });
  });
};

app.get('/', function(req, res){
  res.send('Welcome to the eeger key process tool!');
});
app.get('/healthcheck', function(req, res){
  res.send({status:'Healthy'});
});

app.post('/api/v1/check_status', function (req, res) {
  console.log('Checking status');
  var response = function(stdout, stderr, res){
    console.log(`stdout: ` + stdout);
    console.log(`stderr: ` + stderr);
    res.status(200).send(stdout)
  };
  callPython(req, res, {suffix: '.ekx', dir: tempCheckDir}, 'parseekb.py', response);
});

var port = process.env.PORT || 3000;
app.listen(port, function () {
  console.log('Example app listening on port '+ port + '!');
});
